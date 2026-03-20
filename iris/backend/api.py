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
from typing import Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
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


# ── Retriever helper ─────────────────────────────────────────

def _get_retriever() -> SQLiteRetriever:
    return SQLiteRetriever(DB_PATH)


# ── Ticker extraction helper ────────────────────────────────

def _extract_ticker(query: str, session: AnalysisSession) -> str | None:
    """Best-effort ticker extraction from query and tool results."""
    tool_results = session.accumulated_panels
    for tool_name in ["yf_quote", "build_dcf", "fmp_get_financials"]:
        result = tool_results.get(tool_name, {})
        if isinstance(result, dict) and result.get("ticker"):
            return result["ticker"].upper()
    match = re.search(r'\b([A-Z]{1,5})\b', query)
    return match.group(1) if match else None


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
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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


class KnowledgeUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[list[str]] = None


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

    # Save valuation record if build_dcf was called
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

    # Use accumulated reasoning text, or fall back to result.reply
    reasoning_text = snap["reasoning_text"] or result.reply or ""

    # Extract recommendation from the final reasoning text
    rec = _extract_recommendation(reasoning_text)

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
    )


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
    return {"exists": True, "status": session.status, "query": session.query}


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
            ticker = _extract_ticker(snap.get("reasoning_text", ""), session)
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
    """Build watchlist from DB (structured data) + live yf_quote prices."""
    from tools.market import yf_quote

    retriever = _get_retriever()
    tickers = retriever.get_tracked_tickers()
    if not tickers:
        return []

    loop = asyncio.get_event_loop()

    async def fetch_quote(t: str) -> dict:
        try:
            result = await loop.run_in_executor(None, functools.partial(yf_quote, t))
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
    del run["timeline_json"]
    del run["panels_json"]
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
):
    """List all knowledge documents."""
    retriever = _get_retriever()
    return retriever.list_documents(company=company, doc_type=doc_type)


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
    )
    return result


@app.post("/api/knowledge/upload-url")
async def upload_knowledge_url(req: KnowledgeUrlRequest):
    """Fetch URL content and save to the knowledge base."""
    from tools.search import web_fetch

    fetch_result = web_fetch(url=req.url)
    if fetch_result.status != "ok":
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {fetch_result.error}")

    content = fetch_result.data.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Fetched URL content is empty")

    title = req.title or fetch_result.data.get("title", req.url)

    retriever = _get_retriever()
    result = retriever.save_document(
        title=title,
        doc_type="url",
        content_text=content,
        source_path=req.url,
        company=req.company,
        tags=req.tags,
    )
    return result


from fastapi import File, Form, UploadFile


@app.post("/api/knowledge/upload-file")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    title: str = Form(None),
    company: str = Form(None),
    tags: str = Form(None),
):
    """Upload a file (PDF or text) to the knowledge base."""
    content_bytes = await file.read()
    filename = file.filename or "untitled"

    # Determine doc_type and extract text
    if filename.lower().endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            content_text = "\n\n".join(pages_text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e}")
        doc_type = "pdf"
    else:
        # Assume text-based file
        try:
            content_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content_text = content_bytes.decode("utf-8", errors="replace")
        doc_type = "report"

    if not content_text.strip():
        raise HTTPException(status_code=400, detail="Extracted content is empty")

    effective_title = title or filename
    tag_list = json.loads(tags) if tags else None

    retriever = _get_retriever()
    result = retriever.save_document(
        title=effective_title,
        doc_type=doc_type,
        content_text=content_text,
        source_path=filename,
        company=company,
        tags=tag_list,
    )
    return result


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


# ── Session cleanup background task ─────────────────────────

_cleanup_thread: threading.Thread | None = None


def _cleanup_loop():
    """Remove sessions inactive for >30 minutes. Runs every 60 seconds."""
    while True:
        time.sleep(60)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        sessions = all_sessions()
        for sid, session in sessions.items():
            if session.last_activity < cutoff:
                remove_session(sid)
