"""
IRIS FastAPI backend — REST + SSE API wrapping the Harness agent loop.
"""
from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import asyncio
import functools
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import get as config_get, DB_PATH
from core.harness import HarnessEvent
from backend.sessions import (
    AnalysisSession,
    all_sessions,
    create_session,
    get_session,
    register_session,
    remove_session,
)
from backend.sse_bridge import harness_event_to_sse
from backend.user_input_tool import (
    REQUEST_USER_INPUT_SCHEMA,
    request_user_input,
)
from tools.base import Tool
from tools.memory import check_calibration
from tools.retrieval import SQLiteRetriever
from tools.url_ingest import ingest_url_document


# ── Retriever helper ─────────────────────────────────────────

def _get_retriever() -> SQLiteRetriever:
    return SQLiteRetriever(DB_PATH)


# ── Metadata extraction via LLM ─────────────────────────────

def _extract_metadata_via_llm(query: str, reasoning_text: str) -> dict:
    """Use a lightweight LLM call to extract structured metadata from analysis results.

    Returns dict with keys: ticker, recommendation, confidence.
    """
    import os
    from core.tracing import is_enabled as _lf_ok
    try:
        if _lf_ok():
            from langfuse.openai import OpenAI
        else:
            from openai import OpenAI
    except Exception:
        from openai import OpenAI

    model = os.getenv("METADATA_MODEL") or os.getenv("INGEST_METADATA_MODEL") or "gpt-5.4-mini"
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    excerpt = (reasoning_text or "")[:3000]

    try:
        from core.config import get_prompt
        prompt = get_prompt(
            "iris-metadata-extraction",
            "prompts.metadata_extraction",
            "Extract structured metadata from an investment analysis. "
            "Return JSON with keys: ticker, recommendation, confidence.",
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nAnalysis excerpt:\n{excerpt}",
                },
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        return {
            "ticker": parsed.get("ticker") or None,
            "recommendation": parsed.get("recommendation") or None,
            "confidence": parsed.get("confidence") or None,
        }
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return {"ticker": None, "recommendation": None, "confidence": None}


# ── Mini LLM tool-call loop (gpt-5.4-mini) ────────────────────

def _get_mini_client():
    """Create an OpenAI client for lightweight tool-call tasks."""
    import os
    from core.tracing import is_enabled as _lf_ok
    try:
        if _lf_ok():
            from langfuse.openai import OpenAI
        else:
            from openai import OpenAI
    except Exception:
        from openai import OpenAI

    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    ), os.getenv("MINI_MODEL", "gpt-5.4-mini")


def _mini_llm_tools_sync(
    prompt: str,
    tools: list,
    max_rounds: int = 3,
) -> list[dict]:
    """Run a lightweight LLM tool-call loop.

    Sends *prompt* to gpt-5.4-mini with the given Tool objects,
    executes every tool_call the model emits, feeds results back,
    and repeats until the model stops calling tools or *max_rounds*.

    Returns the list of collected tool-result dicts (ToolResult.data).
    """
    client, model = _get_mini_client()
    tool_schemas = [t.schema for t in tools]
    tool_map = {t.name: t for t in tools}

    messages = [{"role": "user", "content": prompt}]
    collected: list[dict] = []

    for round_i in range(max_rounds):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_schemas or None,
                tool_choice="required" if tool_schemas and round_i == 0 else "auto",
                temperature=0,
            )
        except Exception as e:
            logger.warning(f"mini_llm_tools: LLM call failed round {round_i}: {e}")
            break

        msg = resp.choices[0].message
        if not msg.tool_calls:
            break

        logger.info(f"mini_llm_tools round {round_i}: {len(msg.tool_calls)} tool calls")

        # Append assistant message with tool_calls
        messages.append(msg.model_dump(exclude_none=True))

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            tool = tool_map.get(fn_name)
            if tool:
                try:
                    result = tool.execute(fn_args)
                except Exception as e:
                    logger.warning(f"mini_llm_tools: tool {fn_name}({fn_args}) raised: {e}")
                    result_dict = {"status": "error", "error": str(e)}
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result_dict)})
                    continue
                result_dict = result.to_dict()
                if result.status == "ok":
                    collected.append(result.data)
                else:
                    logger.warning(f"mini_llm_tools: tool {fn_name}({fn_args}) error: {result.error}")
            else:
                result_dict = {"status": "error", "error": f"Unknown tool: {fn_name}"}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result_dict, ensure_ascii=False, default=str),
            })

    logger.info(f"mini_llm_tools: collected {len(collected)} results")
    return collected


async def _mini_llm_tools(
    prompt: str,
    tools: list,
    max_rounds: int = 3,
) -> list[dict]:
    """Async wrapper — runs the sync LLM loop in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(_mini_llm_tools_sync, prompt, tools, max_rounds),
    )


def _classify_query_via_llm(query: str) -> dict:
    """Classify whether a query is a greeting/meta question or a real analysis request.

    Returns dict with keys: is_meta (bool), reply (str or None).
    Uses a fast LLM call instead of brittle regex matching.
    """
    import os
    from core.tracing import is_enabled as _lf_ok
    try:
        if _lf_ok():
            from langfuse.openai import OpenAI
        else:
            from openai import OpenAI
    except Exception:
        from openai import OpenAI

    q = (query or "").strip()
    if not q:
        return {"is_meta": False, "reply": None}

    # Short-circuit: queries longer than 30 chars are almost certainly not greetings
    if len(q) > 30:
        return {"is_meta": False, "reply": None}

    model = os.getenv("METADATA_MODEL") or os.getenv("INGEST_METADATA_MODEL") or "gpt-5.4-mini"
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    try:
        from core.config import get_prompt
        classifier_prompt = get_prompt(
            "iris-classifier",
            "prompts.classifier",
            "You are a classifier for an investment analysis assistant called IRIS. "
            "Determine if the user's message is a greeting/meta question (NOT an analysis request). "
            "Return JSON: {\"is_meta\": bool, \"reply\": string or null}. "
            "is_meta=true ONLY for: greetings (hi, hello, 你好, etc.), "
            "identity questions (who are you, 你是谁), capability questions (what can you do, 你能做什么). "
            "is_meta=false for ANYTHING that could be an analysis request, even if it starts with a greeting "
            "(e.g. 'hello, analyze NVDA' → is_meta=false). "
            "If is_meta=true, provide a friendly reply in the same language as the query. "
            "Introduce yourself as IRIS, an investment research analysis assistant. "
            "Mention you can do: stock/industry analysis, valuation, earnings review, multi-turn follow-up.",
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": classifier_prompt},
                {"role": "user", "content": q},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        return {
            "is_meta": bool(parsed.get("is_meta", False)),
            "reply": parsed.get("reply") if parsed.get("is_meta") else None,
        }
    except Exception as e:
        logger.warning(f"Meta query classification failed: {e}")
        return {"is_meta": False, "reply": None}


# ── App setup ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start cleanup thread on startup."""
    global _cleanup_thread
    _cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    _cleanup_thread.start()
    yield


app = FastAPI(title="IRIS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"(chrome-extension|moz-extension)://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    contextDocs: Optional[list[str]] = None
    mode: Optional[str] = "analysis"
    deep_research: Optional[bool] = False


class AnalyzeResponse(BaseModel):
    analysisId: str
    streamUrl: str


class SteerRequest(BaseModel):
    message: str


class RespondRequest(BaseModel):
    response: str


class MemoryWriteRequest(BaseModel):
    content: str


class KnowledgeNoteRequest(BaseModel):
    title: str
    content: str
    company: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = "other"
    industry: Optional[str] = None


class KnowledgeUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[list[str]] = None
    page_html: Optional[str] = None
    source_type: Optional[str] = None
    force_reingest: Optional[bool] = False


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    company: Optional[str] = None


# ── Memory helpers ───────────────────────────────────────────

_MEMORY_TYPES = ("companies", "sectors", "patterns", "calibration")


def _memory_base() -> Path:
    base = config_get("memory.base_dir", "./memory")
    return Path(base)


def _validate_memory_type(memory_type: str) -> None:
    if memory_type not in _MEMORY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory type: {memory_type}. Must be one of {_MEMORY_TYPES}",
        )


def _memory_file_path(memory_type: str, filename: str) -> Path:
    _validate_memory_type(memory_type)
    base = _memory_base()
    return base / memory_type / filename


logger = logging.getLogger(__name__)


# ── DB persistence helper ────────────────────────────────────

def _save_to_db(session: AnalysisSession, snap: dict, result) -> None:
    """Persist analysis results to the retriever DB. Shared by initial run and continuations."""
    retriever = _get_retriever()

    # Use accumulated reasoning text, or fall back to result.reply
    reasoning_text = snap["reasoning_text"] or result.reply or ""

    # Skip expensive LLM extraction for trivial/meta queries (no tools used, no reasoning)
    has_substance = bool(reasoning_text.strip()) and (
        getattr(result, "tool_log", None) or snap.get("timeline")
    )
    if has_substance:
        metadata = _extract_metadata_via_llm(session.query, reasoning_text)
        ticker = metadata["ticker"]
        rec = metadata["recommendation"]
    else:
        ticker = None
        rec = None

    # Save valuation record if valuation model was produced
    if session.pending_valuation and ticker:
        pv = session.pending_valuation
        fv = pv.get("fair_value") or pv.get("fair_value_per_share")
        if fv is not None:
            retriever.save_valuation_record(
                ticker=ticker,
                fair_value=fv,
                current_price=pv.get("current_price", 0),
                gap_pct=pv.get("gap_pct", 0),
                run_id=session.id,
            )
            # Auto-save prediction to unified memory
            try:
                retriever.save_knowledge_item(
                    type="prediction",
                    subject=ticker,
                    content=f"Fair value prediction: ${fv:.2f}/share",
                    structured_data={
                        "metric": "fair_value",
                        "predicted": fv,
                        "actual": None,
                        "current_price": pv.get("current_price", 0),
                        "review_after": (
                            datetime.now(timezone.utc) + timedelta(days=90)
                        ).strftime("%Y-%m-%d"),
                        "run_id": session.id,
                    },
                    source=f"valuation in {session.id}",
                )
            except Exception:
                pass  # best-effort

    # Serialize conversation messages for resumability
    messages_json = None
    try:
        if hasattr(session.harness, '_messages') and session.harness._messages:
            messages_json = json.dumps(session.harness._messages, ensure_ascii=False, default=str)
    except Exception:
        pass  # best-effort — don't block persistence

    # Save the full analysis run
    retriever.save_analysis_run(
        id=session.id,
        query=session.query,
        ticker=ticker,
        status="complete" if result.ok else "error",
        reasoning_text=reasoning_text,
        thinking_text=snap["thinking_text"],
        timeline_json=json.dumps(snap["timeline"], ensure_ascii=False, default=str),
        panels_json=json.dumps(snap["panels"], ensure_ascii=False, default=str),
        recommendation=rec,
        tokens_in=result.total_input_tokens,
        tokens_out=result.total_output_tokens,
        messages_json=messages_json,
        turn_count=session.turn_count + 1,
    )

    # Auto-save analysis summary as a knowledge note for future recall
    if ticker and reasoning_text:
        try:
            summary = reasoning_text[-2000:] if len(reasoning_text) > 2000 else reasoning_text
            retriever.save_knowledge_item(
                type="note",
                subject=ticker,
                content=summary,
                structured_data={
                    "note_category": "company",
                    "run_id": session.id,
                    "auto_generated": True,
                },
                source=f"analysis_run:{session.id}",
            )
        except Exception:
            pass  # best-effort


# ── Analysis endpoints ───────────────────────────────────────

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analysis(req: AnalyzeRequest):
    """Start a new analysis run. Returns session ID and SSE stream URL."""
    from main import build_harness

    # Validate mode
    mode = req.mode or "analysis"
    if mode not in ("analysis", "learning"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    # Build harness with event callback that feeds the session queue
    harness, _retriever = build_harness(streaming=True, mode=mode)

    session = create_session(harness, query=req.query)

    # Create the on_event callback that pushes to session.events
    def on_event(event: HarnessEvent) -> None:
        try:
            sse = harness_event_to_sse(event)
            if sse is not None:
                session.events.put(sse)
                session.touch()
        except Exception:
            pass  # SSE serialization errors should not block accumulation
        try:
            session.accumulate_raw(event)  # raw event, not truncated
        except Exception:
            pass  # Log but don't crash the harness

    harness.on_event = on_event

    # Register request_user_input as an additional tool with session bound
    bound_fn = functools.partial(request_user_input, session=session)
    user_input_tool = Tool(bound_fn, REQUEST_USER_INPUT_SCHEMA)
    harness.tool_registry[user_input_tool.name] = user_input_tool

    register_session(session)

    # Run harness in background thread
    def _run():
        try:
            meta = _classify_query_via_llm(req.query)
            if meta["is_meta"] and meta["reply"]:
                reply = meta["reply"]
                session._raw_text = reply
                session.events.put({
                    "event": "system",
                    "data": {"message": "已识别为问候/能力咨询，使用轻量回复模式"},
                })
                # Initialize _messages so continue_run works for follow-up turns
                harness._messages = [
                    harness.context.build_system_message(harness.soul, []),
                    {"role": "user", "content": req.query},
                    {"role": "assistant", "content": reply},
                ]
                result = SimpleNamespace(
                    ok=True,
                    reply=reply,
                    error=None,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    tool_log=[],
                )
                snap = session.snapshot()
                _save_to_db(session, snap, result=result)
                session.events.put({
                    "event": "analysis_complete",
                    "data": {
                        "ok": True,
                        "reply": reply,
                        "error": None,
                        "runId": None,
                        "totalInputTokens": 0,
                        "totalOutputTokens": 0,
                        "toolLog": [],
                    },
                })
                session.status = "idle"
                return

            result = harness.run(
                req.query,
                context_docs=req.contextDocs,
                deep_research=req.deep_research or False,
            )

            # --- Persist to DB ---
            snap = session.snapshot()
            _save_to_db(session, snap, result)

            session.events.put({
                "event": "analysis_complete",
                "data": {
                    "ok": result.ok,
                    "reply": result.reply,
                    "error": result.error,
                    "runId": result.run_id,
                    "totalInputTokens": result.total_input_tokens,
                    "totalOutputTokens": result.total_output_tokens,
                    "toolLog": result.tool_log,
                },
            })
            session.status = "idle"
        except Exception as e:
            session.events.put({
                "event": "error",
                "data": {
                    "message": str(e),
                    "recoverable": False,
                },
            })
            session.status = "error"
        finally:
            # Sentinel to signal SSE stream end
            session.events.put(None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return AnalyzeResponse(
        analysisId=session.id,
        streamUrl=f"/api/analyze/{session.id}/stream",
    )


@app.get("/api/analyze/{analysis_id}/stream")
async def stream_events(analysis_id: str):
    """SSE endpoint — streams harness events to the client."""
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Analysis session not found")

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            try:
                # Read from threading.Queue in executor to avoid blocking event loop
                event = await loop.run_in_executor(None, functools.partial(session.events.get, timeout=30))
            except Exception:
                # Queue.get timeout — send keepalive
                yield ": keepalive\n\n"
                continue

            if event is None:
                # Sentinel: stream end
                yield f"event: done\ndata: {{}}\n\n"
                break

            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False, default=str)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/analyze/{analysis_id}/status")
async def session_status(analysis_id: str):
    """Lightweight probe: does this session exist?"""
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "exists": True,
        "status": session.status,
        "query": session.query,
        "continuable": session.status in ("idle", "complete", "error"),
        "turn_count": session.turn_count,
    }


@app.post("/api/analyze/{analysis_id}/steer")
async def steer_analysis(analysis_id: str, req: SteerRequest):
    """Inject a steering message into the running analysis."""
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Analysis session not found")

    session.harness.steer(req.message)
    session.touch()
    return {"ok": True}


@app.post("/api/analyze/{analysis_id}/respond")
async def respond_to_input(analysis_id: str, req: RespondRequest):
    """Respond to a user_input_needed event from the harness."""
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Analysis session not found")

    if session.status != "waiting":
        raise HTTPException(status_code=400, detail="Session is not waiting for input")

    session.user_input_response = req.response
    session.user_input_event.set()
    session.touch()
    return {"ok": True}


@app.post("/api/analyze/{analysis_id}/continue")
async def continue_analysis(analysis_id: str, req: SteerRequest):
    """Continue a completed analysis with a follow-up message."""
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.status == "running":
        raise HTTPException(status_code=400, detail="Session is still running")

    session.status = "running"
    session.turn_count += 1

    # Record the user message + turn markers so the full multi-turn
    # conversation is persisted in reasoning_text for replay.
    session.inject_turn(req.message)

    # Re-create event callback
    def on_event(event: HarnessEvent) -> None:
        try:
            sse = harness_event_to_sse(event)
            if sse:
                session.events.put(sse)
                session.touch()
            session.accumulate_raw(event)
        except Exception as e:
            logger.error(f"Event callback error: {e}")

    def run_continuation():
        try:
            result = session.harness.continue_run(
                user_input=req.message,
                on_event=on_event,
            )
            # Save updated snapshot
            snap = session.snapshot()
            _save_to_db(session, snap, result)

            session.events.put({
                "event": "analysis_complete",
                "data": {
                    "ok": result.ok,
                    "reply": result.reply,
                    "error": result.error,
                    "runId": result.run_id,
                    "totalInputTokens": result.total_input_tokens,
                    "totalOutputTokens": result.total_output_tokens,
                    "toolLog": result.tool_log,
                    "turn": session.turn_count,
                },
            })
            session.status = "idle"
        except Exception as e:
            logger.exception(f"Continuation failed: {e}")
            session.events.put({"event": "error", "data": {"message": str(e)}})
            session.status = "error"
        finally:
            session.events.put(None)

    thread = threading.Thread(target=run_continuation, daemon=True)
    thread.start()

    return {"status": "continuing", "turn": session.turn_count}


@app.post("/api/analyze/{run_id}/resume")
async def resume_analysis(run_id: str, req: SteerRequest):
    """Resume a conversation from DB history. Rehydrates the session if expired."""
    # 1. If session is still alive in memory, delegate to /continue
    session = get_session(run_id)
    if session is not None:
        if session.status == "running":
            raise HTTPException(status_code=400, detail="Session is still running")
        # Delegate to continue logic
        return await continue_analysis(run_id, req)

    # 2. Load from DB
    retriever = _get_retriever()
    run = retriever.get_analysis_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    messages_json_str = run.get("messages_json")
    if not messages_json_str:
        raise HTTPException(
            status_code=409,
            detail="此对话无法恢复（缺少对话历史），请发起新分析",
        )

    # 3. Rehydrate: build a fresh harness and restore conversation state
    from main import build_harness

    harness, _retriever = build_harness(streaming=True)

    try:
        harness._messages = json.loads(messages_json_str)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=409, detail="对话历史数据损坏，请发起新分析")

    session = create_session(harness, query=run.get("query", ""))
    # Use the SAME id so DB row is updated in-place
    session.id = run_id
    session.turn_count = run.get("turn_count", 1)
    session.status = "running"

    # Restore accumulated state from DB snapshot
    try:
        session.accumulated_timeline = json.loads(run.get("timeline_json") or "[]")
        # Reconstruct _raw_text with thinking tags so _split_thinking_blocks works correctly
        reasoning = run.get("reasoning_text") or ""
        # Reconstruct turn markers for legacy multi-turn data
        reasoning = _reconstruct_turns(reasoning, run.get("messages_json", ""))
        thinking = run.get("thinking_text") or ""
        session._raw_text = reasoning + (f"\n<thinking>\n{thinking}\n</thinking>" if thinking else "")
        panels = json.loads(run.get("panels_json") or "{}")
        for key in ("data", "model", "comps", "strategy", "memory", "fundamentals"):
            if key in panels:
                session.accumulated_frontend_panels[key] = panels[key]
    except Exception:
        pass  # best-effort restore

    # Set up event callback
    def on_event(event: HarnessEvent) -> None:
        try:
            sse = harness_event_to_sse(event)
            if sse is not None:
                session.events.put(sse)
                session.touch()
        except Exception:
            pass
        try:
            session.accumulate_raw(event)
        except Exception:
            pass

    harness.on_event = on_event

    # Register user_input tool
    bound_fn = functools.partial(request_user_input, session=session)
    user_input_tool = Tool(bound_fn, REQUEST_USER_INPUT_SCHEMA)
    harness.tool_registry[user_input_tool.name] = user_input_tool

    # Record the user message + turn markers for replay persistence.
    session.inject_turn(req.message)

    register_session(session)

    # 4. Run continuation in background thread
    def _run_resume():
        try:
            result = harness.continue_run(
                user_input=req.message,
                on_event=on_event,
            )
            snap = session.snapshot()
            _save_to_db(session, snap, result)

            session.events.put({
                "event": "analysis_complete",
                "data": {
                    "ok": result.ok,
                    "reply": result.reply,
                    "error": result.error,
                    "runId": result.run_id,
                    "totalInputTokens": result.total_input_tokens,
                    "totalOutputTokens": result.total_output_tokens,
                    "toolLog": result.tool_log,
                    "turn": session.turn_count,
                },
            })
            session.status = "idle"
        except Exception as e:
            logger.exception(f"Resume failed: {e}")
            session.events.put({"event": "error", "data": {"message": str(e)}})
            session.status = "error"
        finally:
            session.events.put(None)

    thread = threading.Thread(target=_run_resume, daemon=True)
    thread.start()

    return {
        "analysisId": session.id,
        "streamUrl": f"/api/analyze/{session.id}/stream",
        "status": "resuming",
        "turn": session.turn_count,
    }


# ── Trade execution endpoint ─────────────────────────────────

class ExecuteTradeRequest(BaseModel):
    ticker: str
    action: str  # "BUY" or "SELL"
    shares: int
    price: float


@app.post("/api/trade/execute")
async def execute_trade(req: ExecuteTradeRequest):
    """Execute a paper trade (user-confirmed from UI)."""
    from skills.trading.tools import execute_trade as _exec_trade
    result = _exec_trade(
        ticker=req.ticker,
        action=req.action,
        shares=req.shares,
        price=req.price,
    )
    if result.status != "ok":
        raise HTTPException(status_code=400, detail=result.error or "Trade failed")
    return result.data


@app.get("/api/portfolio")
async def get_portfolio_api():
    """Get current portfolio state with concurrent live prices."""
    from skills.trading.tools import get_portfolio as _get_portfolio, _load_portfolio
    from tools.market import quote as quote_fn

    portfolio_raw = _load_portfolio()
    tickers = list(portfolio_raw.get("positions", {}).keys())
    live_prices: dict[str, float] = {}

    if tickers:
        loop = asyncio.get_running_loop()

        async def _fetch(tk: str) -> tuple[str, float | None]:
            try:
                result = await loop.run_in_executor(None, quote_fn, tk)
                if result.status == "ok" and result.data.get("price"):
                    return tk.upper(), result.data["price"]
            except Exception as e:
                logger.warning(f"portfolio quote({tk}) failed: {e}")
            return tk.upper(), None

        results = await asyncio.gather(*[_fetch(tk) for tk in tickers])
        live_prices = {tk: p for tk, p in results if p is not None}

    result = _get_portfolio(live_prices=live_prices)
    return result.data


# ── Memory endpoints ─────────────────────────────────────────

@app.get("/api/memory")
async def list_memory():
    """Scan memory directory tree and return organized structure."""
    base = _memory_base()
    result = {
        "companies": [],
        "sectors": [],
        "patterns": [],
        "calibration": [],
    }

    for memory_type in _MEMORY_TYPES:
        type_dir = base / memory_type
        if not type_dir.exists():
            continue
        for f in sorted(type_dir.iterdir()):
            if f.is_file():
                result[memory_type].append(f.name)

    return result


@app.get("/api/memory/{memory_type}/{filename}")
async def read_memory(memory_type: str, filename: str):
    """Read a specific memory file."""
    path = _memory_file_path(memory_type, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {memory_type}/{filename}")

    content = path.read_text(encoding="utf-8")
    return {"content": content, "path": f"{memory_type}/{filename}"}


@app.put("/api/memory/{memory_type}/{filename}")
async def write_memory(memory_type: str, filename: str, req: MemoryWriteRequest):
    """Write content to a memory file."""
    path = _memory_file_path(memory_type, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"ok": True, "path": f"{memory_type}/{filename}"}


@app.delete("/api/memory/{memory_type}/{filename}")
async def delete_memory(memory_type: str, filename: str):
    """Delete a memory file."""
    path = _memory_file_path(memory_type, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {memory_type}/{filename}")

    path.unlink()
    return {"ok": True, "path": f"{memory_type}/{filename}"}


# ── Watchlist endpoint ───────────────────────────────────────

@app.get("/api/watchlist")
async def get_watchlist():
    """Build watchlist from DB (structured data) + direct concurrent quotes."""
    from tools.market import quote as quote_fn

    retriever = _get_retriever()
    tickers = retriever.get_tracked_tickers()
    if not tickers:
        return []

    # Fetch all quotes concurrently — no LLM needed for simple price lookup
    loop = asyncio.get_running_loop()

    async def _fetch_quote(tk: str) -> tuple[str, dict]:
        try:
            result = await loop.run_in_executor(None, quote_fn, tk)
            if result.status == "ok":
                return tk.upper(), result.data
        except Exception as e:
            logger.warning(f"watchlist quote({tk}) failed: {e}")
        return tk.upper(), {}

    quote_tasks = [_fetch_quote(tk) for tk in tickers]
    quote_results = await asyncio.gather(*quote_tasks)
    quote_map: dict[str, dict] = {tk: data for tk, data in quote_results}

    watchlist = []
    for ticker in tickers:
        q = quote_map.get(ticker.upper(), {})
        val = retriever.get_latest_valuation(ticker)
        latest_run = retriever.get_latest_run_for_ticker(ticker)
        hyps = retriever.list_hypotheses(company=ticker)
        thesis = hyps[-1].thesis if hyps else None

        # Parse fair_value from the valuation data JSON
        fair_value = None
        if val:
            val_data = val.get("data")
            if val_data and isinstance(val_data, str):
                try:
                    parsed = json.loads(val_data)
                    fair_value = parsed.get("fair_value")
                except (json.JSONDecodeError, TypeError):
                    pass
            elif val_data and isinstance(val_data, dict):
                fair_value = val_data.get("fair_value")

        # Discard clearly invalid fair_value (0 or negative)
        if fair_value is not None and fair_value <= 0:
            fair_value = None

        market_price = q.get("price")
        gap = None
        if fair_value is not None and market_price is not None and market_price != 0:
            gap = round((fair_value - market_price) / market_price, 4)

        watchlist.append({
            "ticker": ticker,
            "name": q.get("name"),
            "market_price": market_price,
            "fair_value": fair_value,
            "gap": gap,
            "thesis": thesis,
            "recommendation": latest_run.get("recommendation") if latest_run else None,
            "latest_run_id": latest_run["id"] if latest_run else None,
            "alerts": [],
        })
    return watchlist


# ── History endpoints ────────────────────────────────────────

@app.get("/api/history")
async def list_history(
    ticker: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    retriever = _get_retriever()
    return retriever.list_analysis_runs(ticker=ticker, limit=limit, offset=offset)


def _reconstruct_turns(reasoning_text: str, messages_json_str: str) -> str:
    """Reconstruct reasoning_text with <!---TURN---> markers from messages_json.

    For conversations saved before turn markers were persisted, this function
    extracts user follow-up messages and assistant text anchors from the message
    history, then inserts turn markers at the correct positions in reasoning_text.
    """
    if not messages_json_str or "<!---TURN--->" in (reasoning_text or ""):
        return reasoning_text or ""

    try:
        messages = json.loads(messages_json_str)
    except (json.JSONDecodeError, TypeError):
        return reasoning_text or ""

    # Collect turn boundaries: (user_messages[], assistant_anchor_text)
    # A turn boundary is a group of user messages followed by assistant responses.
    # We scan ALL subsequent assistant messages (not just the first) to find a
    # visible text anchor, since intermediate assistants may contain only thinking.
    import re as _re
    turns: list[tuple[list[str], str]] = []
    past_initial_assistant = False
    current_user_msgs: list[str] = []
    seeking_anchor = False  # True when we have user msgs but no anchor yet

    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            if not past_initial_assistant:
                past_initial_assistant = True
                continue
            if current_user_msgs and not seeking_anchor:
                # First assistant after user follow-ups
                content = msg.get("content", "") or ""
                anchor = _re.sub(r"<thinking>[\s\S]*?</thinking>", "", content).strip()
                if anchor:
                    turns.append((current_user_msgs.copy(), anchor))
                    current_user_msgs = []
                else:
                    seeking_anchor = True
            elif seeking_anchor:
                # Keep looking for visible text in later assistant messages
                content = msg.get("content", "") or ""
                anchor = _re.sub(r"<thinking>[\s\S]*?</thinking>", "", content).strip()
                if anchor:
                    turns.append((current_user_msgs.copy(), anchor))
                    current_user_msgs = []
                    seeking_anchor = False
        elif role == "user" and past_initial_assistant:
            if seeking_anchor:
                # Hit next user message without finding anchor — save turn without anchor
                turns.append((current_user_msgs.copy(), ""))
                current_user_msgs = []
                seeking_anchor = False
            current_user_msgs.append(msg.get("content", "") or "")

    # Flush any remaining user messages without anchor
    if current_user_msgs:
        turns.append((current_user_msgs, ""))

    if not turns:
        return reasoning_text or ""

    # Insert markers using anchors (process in reverse to keep positions stable)
    result = reasoning_text or ""
    for user_msgs, anchor in reversed(turns):
        combined_user = "\n".join(m for m in user_msgs if m.strip())
        if not combined_user.strip():
            continue
        marker = f"\n\n<!---TURN--->\n{combined_user}\n<!---TURN--->\n\n"

        if anchor and anchor in result:
            idx = result.index(anchor)
            result = result[:idx] + marker + result[idx:]
        else:
            # Fallback: search for substrings of the user's message in the AI text.
            # The AI often quotes or paraphrases the user, e.g. 关于你说的"全部减仓".
            # Try sliding windows of decreasing length over the longest user message.
            longest_msg = max(user_msgs, key=len).strip()
            found = False
            min_window = min(3, len(longest_msg))
            for window in range(len(longest_msg), min_window - 1, -1):
                for start in range(len(longest_msg) - window + 1):
                    needle = longest_msg[start : start + window]
                    idx = result.rfind(needle)
                    if idx > 0:
                        # Walk back to start of paragraph
                        linebreak = result.rfind("\n", 0, idx)
                        split_at = linebreak + 1 if linebreak > 0 else idx
                        result = result[:split_at] + marker + result[split_at:]
                        found = True
                        break
                if found:
                    break

    return result


@app.get("/api/history/{run_id}")
async def get_history_detail(run_id: str):
    retriever = _get_retriever()
    run = retriever.get_analysis_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    run["timeline"] = json.loads(run.get("timeline_json") or "[]")
    run["panels"] = json.loads(run.get("panels_json") or "{}")
    run["resumable"] = bool(run.get("messages_json"))
    run["turn_count"] = run.get("turn_count", 1)

    # Reconstruct turn markers for legacy multi-turn conversations
    if run.get("turn_count", 1) > 1:
        run["reasoning_text"] = _reconstruct_turns(
            run.get("reasoning_text", ""),
            run.get("messages_json", ""),
        )

    # Remove heavy/internal fields from response
    run.pop("timeline_json", None)
    run.pop("panels_json", None)
    run.pop("messages_json", None)
    return run


# ── Calibration endpoint ─────────────────────────────────────

@app.get("/api/calibration")
async def get_calibration(company: Optional[str] = Query(default=None)):
    """Delegate to check_calibration() tool."""
    result = check_calibration(company=company)
    return result.to_dict()


# ── Knowledge endpoints ──────────────────────────────────

@app.get("/api/knowledge")
async def list_knowledge(
    company: Optional[str] = Query(default=None),
    doc_type: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None),
):
    """List all knowledge documents."""
    retriever = _get_retriever()
    return retriever.list_documents(company=company, doc_type=doc_type, category=category, industry=industry)


@app.get("/api/knowledge/{doc_id}")
async def get_knowledge_doc(doc_id: str):
    """Get a specific knowledge document with full content."""
    retriever = _get_retriever()
    doc = retriever.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.post("/api/knowledge/upload-note")
async def upload_knowledge_note(req: KnowledgeNoteRequest):
    """Upload a text note to the knowledge base."""
    retriever = _get_retriever()
    result = retriever.save_document(
        title=req.title,
        doc_type="note",
        content_text=req.content,
        company=req.company,
        tags=req.tags,
        category=req.category or "other",
        industry=req.industry,
    )
    return result


async def _ingest_url(req: KnowledgeUrlRequest, default_source: str) -> dict:
    """Shared URL ingest logic for upload and import endpoints."""
    retriever = _get_retriever()
    result = ingest_url_document(
        retriever=retriever,
        url=req.url,
        title=req.title,
        page_html=req.page_html,
        source_type=req.source_type or default_source,
        company=req.company,
        tags=req.tags,
        force_reingest=bool(req.force_reingest),
    )
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("detail") or result.get("error") or "URL ingest failed")
    return result


@app.post("/api/knowledge/upload-url")
async def upload_knowledge_url(req: KnowledgeUrlRequest):
    """Fetch URL content and save to the knowledge base."""
    result = await _ingest_url(req, "manual_url")
    doc = result.get("document") or {}
    doc["ingest_status"] = result.get("status")
    if result.get("duplicate_of"):
        doc["duplicate_of"] = result.get("duplicate_of")
    return doc


@app.post("/api/knowledge/import-url")
async def import_knowledge_url(req: KnowledgeUrlRequest):
    """URL import endpoint for browser extension, with explicit ingest status."""
    return await _ingest_url(req, "browser_extension")


@app.post("/api/knowledge/upload-file")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    title: str = Form(None),
    company: str = Form(None),
    tags: str = Form(None),
    category: str = Form(None),
    industry: str = Form(None),
    engine: str = Form(None),
):
    """Upload a file (PDF, Excel, or text) to the knowledge base.

    Uses the multi-engine document parser:
      - PDF: pymupdf4llm (fast) > Docling (precise) > PyPDF2 (fallback)
      - Excel: pandas → Markdown tables
      - Text: direct UTF-8 decode
    """
    from tools.document_parser import parse_file, ParseEngine, available_engines

    content_bytes = await file.read()
    filename = file.filename or "untitled"

    # Select engine
    parse_engine = ParseEngine.AUTO
    if engine and engine in ParseEngine.__members__:
        parse_engine = ParseEngine(engine)

    try:
        result = parse_file(content_bytes, filename, engine=parse_engine)
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"No parser available: {e}. Installed: {available_engines()}",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    content_text = result.content
    if not content_text.strip():
        raise HTTPException(status_code=400, detail="Extracted content is empty")

    # Determine doc_type from file extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    doc_type_map = {"pdf": "pdf", "xlsx": "report", "xls": "report", "csv": "report"}
    doc_type = doc_type_map.get(ext, "report")

    effective_title = title or filename
    tag_list = json.loads(tags) if tags else None

    retriever = _get_retriever()
    save_result = retriever.save_document(
        title=effective_title,
        doc_type=doc_type,
        content_text=content_text,
        source_path=filename,
        company=company,
        tags=tag_list,
        category=category or "other",
        industry=industry,
    )

    # Include parser metadata in response
    save_result["parser"] = {
        "engine": result.engine_used,
        "pages": result.page_count,
        "warnings": result.warnings,
    }
    return save_result


@app.delete("/api/knowledge/{doc_id}")
async def delete_knowledge_doc(doc_id: str):
    """Delete a knowledge document and its chunks."""
    retriever = _get_retriever()
    deleted = retriever.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


@app.post("/api/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    """Search knowledge base for relevant passages."""
    retriever = _get_retriever()
    results = retriever.semantic_search(
        query=req.query,
        top_k=req.top_k or 5,
        source_category="human_knowledge",
    )
    return {"query": req.query, "results": results, "count": len(results)}


# ── Excel download endpoint ──────────────────────────────────

@app.get("/api/download-excel")
async def download_excel(path: str = Query(..., description="Path to the generated .xlsx file")):
    """Stream an Excel workbook generated by the valuation export_excel mode."""
    import os
    from fastapi.responses import FileResponse

    if not os.path.isfile(path) or not path.endswith(".xlsx"):
        raise HTTPException(status_code=404, detail="Excel file not found")
    filename = os.path.basename(path)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


# ── Developer panel endpoints ────────────────────────────────

@app.get("/api/dev/tools")
async def dev_list_tools():
    """List all registered tools with their schemas."""
    from main import build_harness

    harness, _ = build_harness(streaming=False)
    tools = []
    for name, tool in harness.tool_registry.items():
        fn = tool.schema.get("function", {})
        params = fn.get("parameters", {})
        tools.append({
            "name": name,
            "description": fn.get("description", ""),
            "parameters": params.get("properties", {}),
            "required": params.get("required", []),
        })
    return {"tools": tools, "count": len(tools)}


@app.get("/api/dev/skills")
async def dev_list_skills():
    """List all skills with their SKILL.md content."""
    skills_dir = Path(config_get("skills.dir", "./skills"))
    skills = []
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if not d.is_dir():
                continue
            skill_md = d / "SKILL.md"
            tools_py = d / "tools.py"
            skill = {
                "name": d.name,
                "prompt": skill_md.read_text(encoding="utf-8") if skill_md.exists() else "",
                "has_tools": tools_py.exists(),
            }
            # Extract tool function names from tools.py
            if tools_py.exists():
                code = tools_py.read_text(encoding="utf-8")
                import re as re_mod
                fns = re_mod.findall(r"^def\s+(\w+)\s*\(", code, re_mod.MULTILINE)
                schemas = re_mod.findall(r"(\w+_SCHEMA)\s*=", code)
                skill["tool_functions"] = [f for f in fns if not f.startswith("_")]
                skill["schemas"] = schemas
            skills.append(skill)
    return {"skills": skills, "count": len(skills)}


@app.get("/api/dev/soul")
async def dev_list_soul():
    """List all soul prompt files with content."""
    soul_dir = Path(__file__).parent.parent / "soul"
    files = []
    if soul_dir.exists():
        for f in sorted(soul_dir.glob("*.md")):
            files.append({
                "name": f.name,
                "content": f.read_text(encoding="utf-8"),
                "size": f.stat().st_size,
            })
    return {"files": files, "count": len(files)}


@app.put("/api/dev/soul/{filename}")
async def dev_update_soul(filename: str, req: MemoryWriteRequest):
    """Update a soul prompt file."""
    soul_dir = Path(__file__).parent.parent / "soul"
    path = soul_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Soul file not found: {filename}")
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files allowed")
    path.write_text(req.content, encoding="utf-8")
    # Clear config cache so changes take effect
    from core.config import reset_config_cache
    reset_config_cache()
    return {"ok": True, "name": filename}


@app.get("/api/dev/config")
async def dev_get_config():
    """Return the full iris_config.yaml as JSON."""
    from core.config import load_config, reset_config_cache
    reset_config_cache()
    cfg = load_config()
    return cfg


@app.put("/api/dev/config")
async def dev_update_config(req: MemoryWriteRequest):
    """Update iris_config.yaml (expects YAML string)."""
    import yaml as yaml_mod
    # Validate YAML first
    try:
        parsed = yaml_mod.safe_load(req.content)
        if not isinstance(parsed, dict):
            raise ValueError("Config must be a YAML mapping")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    config_path = Path(__file__).parent.parent / "iris_config.yaml"
    config_path.write_text(req.content, encoding="utf-8")
    from core.config import reset_config_cache
    reset_config_cache()
    return {"ok": True}


@app.get("/api/dev/sessions")
async def dev_list_sessions():
    """List all active analysis sessions."""
    sessions = all_sessions()
    result = []
    for sid, s in sessions.items():
        result.append({
            "id": sid,
            "query": s.query,
            "status": s.status,
            "turn_count": s.turn_count,
            "last_activity": s.last_activity.isoformat() if s.last_activity else None,
            "timeline_count": len(s.accumulated_timeline),
        })
    return {"sessions": result, "count": len(result)}


@app.get("/api/dev/stats")
async def dev_system_stats():
    """System statistics: DB size, knowledge count, memory files, etc."""
    import os as os_mod
    retriever = _get_retriever()

    # DB file size
    db_size = 0
    if os_mod.path.exists(DB_PATH):
        db_size = os_mod.path.getsize(DB_PATH)

    # Knowledge doc count
    docs = retriever.list_documents()
    doc_count = len(docs) if docs else 0

    # Memory file count
    base = _memory_base()
    mem_count = 0
    for mt in _MEMORY_TYPES:
        type_dir = base / mt
        if type_dir.exists():
            mem_count += sum(1 for f in type_dir.iterdir() if f.is_file())

    # Analysis run count
    runs = retriever.list_analysis_runs(limit=1000)
    run_count = len(runs) if runs else 0

    # Active sessions
    sessions = all_sessions()

    return {
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "knowledge_docs": doc_count,
        "memory_files": mem_count,
        "analysis_runs": run_count,
        "active_sessions": len(sessions),
        "config_path": str(Path(__file__).parent.parent / "iris_config.yaml"),
    }


# ── Session cleanup background task ─────────────────────────

_cleanup_thread: threading.Thread | None = None


def _cleanup_loop():
    """Remove sessions inactive for >30 minutes. Runs every 60 seconds.
    Saves conversation state before eviction so sessions can be resumed later."""
    while True:
        time.sleep(60)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        sessions = all_sessions()
        for sid, session in sessions.items():
            if session.last_activity < cutoff:
                # Save final state before eviction (best-effort)
                try:
                    if hasattr(session.harness, '_messages') and session.harness._messages:
                        snap = session.snapshot()
                        reasoning_text = snap.get("reasoning_text", "")
                        metadata = _extract_metadata_via_llm(session.query, reasoning_text)
                        messages_json = json.dumps(
                            session.harness._messages, ensure_ascii=False, default=str
                        )
                        retriever = _get_retriever()
                        retriever.save_analysis_run(
                            id=session.id,
                            query=session.query,
                            ticker=metadata["ticker"],
                            status="complete",
                            reasoning_text=reasoning_text,
                            thinking_text=snap.get("thinking_text", ""),
                            timeline_json=json.dumps(
                                snap["timeline"], ensure_ascii=False, default=str
                            ),
                            panels_json=json.dumps(
                                snap["panels"], ensure_ascii=False, default=str
                            ),
                            recommendation=metadata["recommendation"],
                            messages_json=messages_json,
                            turn_count=session.turn_count + 1,
                        )
                except Exception:
                    pass
                remove_session(sid)
