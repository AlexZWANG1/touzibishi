"""
IRIS FastAPI backend — REST + SSE API wrapping the Harness agent loop.
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

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


# ── Ticker extraction helper ────────────────────────────────

def _extract_ticker(query: str, session: AnalysisSession) -> str | None:
    """Best-effort ticker extraction from query and tool results."""
    tool_results = session.accumulated_panels
    # Prefer market-data tools.
    for tool_name in ["quote", "financials", "valuation", "yf_quote", "fmp_get_financials", "build_dcf"]:
        result = tool_results.get(tool_name, {})
        if isinstance(result, dict) and result.get("ticker"):
            return result["ticker"].upper()

    # Fallback: parse raw query symbols, but exclude common finance acronyms.
    blacklist = {
        "DCF", "FCF", "EPS", "EBIT", "EBITDA", "EV", "PE", "PBR", "PB",
        "PS", "ROE", "ROIC", "CAGR", "FY", "TTM", "WACC",
    }
    for candidate in re.findall(r"\b([A-Z]{1,5})\b", query or ""):
        if candidate not in blacklist:
            return candidate
    return None


_META_QUERY_PATTERNS = [
    re.compile(r"^(hi|hello|hey)[!?.\s]*$", re.IGNORECASE),
    re.compile(r"^你好[呀啊吗嘛呢]?[!！。？?\s]*$"),
    re.compile(r"^(您好|嗨|哈喽|在吗|在不在|早上好|下午好|晚上好)[!！。？?\s]*$"),
    re.compile(r"^(who are you|what can you do)[!?.\s]*$", re.IGNORECASE),
    re.compile(r"^(你是谁|你能做什么|你会什么|介绍一下你自己|自我介绍)[!！。？?\s]*$"),
]


def _is_meta_query(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    return any(p.fullmatch(q) for p in _META_QUERY_PATTERNS)


def _build_meta_reply(query: str) -> str:
    q = (query or "").strip().lower()
    if "who are you" in q or "你是谁" in query or "自我介绍" in query:
        return (
            "我是 IRIS，一个面向投研任务的分析助手。"
            "你可以直接说“分析 NVDA”“比较 TSLA 和 AMD”“复盘昨天的策略信号”，"
            "我会按分析流程给出结论、依据和关键数据。"
        )
    return (
        "你好，我可以帮你做股票/行业分析、估值、财报解读和多轮追问。"
        "如果你给我具体标的或问题（例如“分析一下英伟达”），我会直接开始。"
    )


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


# ── Recommendation extraction ────────────────────────────────

_REC_KEYWORDS = [
    "strong buy", "strong sell",
    "buy", "sell", "hold",
    "overweight", "underweight", "equal-weight", "equal weight",
    "outperform", "underperform", "market perform",
    "accumulate", "reduce",
]
_REC_PATTERN = re.compile(
    r"\b(?:recommendation|rating|verdict|conclusion)\s*[:\-–—]\s*"
    r"(" + "|".join(re.escape(k) for k in _REC_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
_REC_FALLBACK = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _REC_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _extract_recommendation(text: str | None) -> str | None:
    """Extract a recommendation keyword (BUY/SELL/HOLD/etc.) from reasoning text."""
    if not text:
        return None
    # Prefer explicit "Recommendation: BUY" style
    m = _REC_PATTERN.search(text)
    if m:
        return m.group(1).upper()
    # Fallback: scan last 500 chars for a standalone keyword
    tail = text[-500:]
    m = _REC_FALLBACK.search(tail)
    if m:
        return m.group(1).upper()
    return None


logger = logging.getLogger(__name__)


# ── DB persistence helper ────────────────────────────────────

def _save_to_db(session: AnalysisSession, snap: dict, ticker: str | None, result) -> None:
    """Persist analysis results to the retriever DB. Shared by initial run and continuations."""
    retriever = _get_retriever()

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

    # Use accumulated reasoning text, or fall back to result.reply
    reasoning_text = snap["reasoning_text"] or result.reply or ""

    # Extract recommendation from the final reasoning text
    rec = _extract_recommendation(reasoning_text)

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
            if _is_meta_query(req.query):
                reply = _build_meta_reply(req.query)
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
                _save_to_db(session, snap, ticker=None, result=result)
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

            result = harness.run(req.query, context_docs=req.contextDocs)

            # --- Persist to DB ---
            snap = session.snapshot()
            ticker = _extract_ticker(req.query, session)
            _save_to_db(session, snap, ticker, result)

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
            ticker = _extract_ticker(session.query, session)
            _save_to_db(session, snap, ticker, result)

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

    register_session(session)

    # 4. Run continuation in background thread
    def _run_resume():
        try:
            result = harness.continue_run(
                user_input=req.message,
                on_event=on_event,
            )
            snap = session.snapshot()
            ticker = _extract_ticker(session.query, session)
            _save_to_db(session, snap, ticker, result)

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
    """Get current paper portfolio state with live prices."""
    from skills.trading.tools import get_portfolio as _get_portfolio, _load_portfolio
    from tools.market import quote as _quote

    # Fetch live prices for all held tickers (same pattern as /api/watchlist)
    portfolio_raw = _load_portfolio()
    tickers = list(portfolio_raw.get("positions", {}).keys())
    live_prices = {}
    if tickers:
        loop = asyncio.get_event_loop()

        async def _fetch(t: str):
            try:
                qr = await loop.run_in_executor(None, functools.partial(_quote, t))
                if qr.status == "ok" and qr.data.get("price"):
                    return t, qr.data["price"]
            except Exception:
                pass
            return t, None

        results = await asyncio.gather(*[_fetch(t) for t in tickers])
        live_prices = {t: p for t, p in results if p is not None}

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
    """Build watchlist from DB (structured data) + live quote prices."""
    from tools.market import quote

    retriever = _get_retriever()
    tickers = retriever.get_tracked_tickers()
    if not tickers:
        return []

    loop = asyncio.get_event_loop()

    async def fetch_quote(t: str) -> dict:
        try:
            result = await loop.run_in_executor(None, functools.partial(quote, t))
            if result.status == "ok":
                return result.data
        except Exception:
            pass
        return {}

    quotes = await asyncio.gather(*[fetch_quote(t) for t in tickers])
    quote_map = {t: q for t, q in zip(tickers, quotes)}

    watchlist = []
    for ticker in tickers:
        quote = quote_map.get(ticker, {})
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

        market_price = quote.get("price")
        gap = None
        if fair_value is not None and market_price is not None and market_price != 0:
            gap = round((fair_value - market_price) / market_price, 4)

        watchlist.append({
            "ticker": ticker,
            "name": quote.get("name"),
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
                        ticker = _extract_ticker(session.query, session)
                        reasoning_text = snap.get("reasoning_text", "")
                        rec = _extract_recommendation(reasoning_text)
                        messages_json = json.dumps(
                            session.harness._messages, ensure_ascii=False, default=str
                        )
                        retriever = _get_retriever()
                        retriever.save_analysis_run(
                            id=session.id,
                            query=session.query,
                            ticker=ticker,
                            status="complete",
                            reasoning_text=reasoning_text,
                            thinking_text=snap.get("thinking_text", ""),
                            timeline_json=json.dumps(
                                snap["timeline"], ensure_ascii=False, default=str
                            ),
                            panels_json=json.dumps(
                                snap["panels"], ensure_ascii=False, default=str
                            ),
                            recommendation=rec,
                            messages_json=messages_json,
                            turn_count=session.turn_count + 1,
                        )
                except Exception:
                    pass
                remove_session(sid)
