"""
Session management for IRIS backend.

Each analysis run gets an AnalysisSession that bridges the harness thread
with the async FastAPI layer via a threading.Queue.

The session also accumulates raw (untruncated) harness event data for
persistence via accumulate_raw().
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from core.harness import EventType, Harness, HarnessEvent


def _default_frontend_panels() -> dict:
    """Return the initial frontend-shaped panel structure."""
    return {
        "data": {"metrics": [], "financialTables": [], "loading": False},
        "model": {
            "fairValue": None,
            "assumptions": [],
            "impliedMultiples": [],
            "sensitivityData": [],
            "sensitivityRowLabel": "WACC",
            "sensitivityColLabel": "Terminal Growth",
            "sensitivityRowValues": [],
            "sensitivityColValues": [],
            "yearByYear": [],
            "loading": False,
        },
        "comps": {
            "peers": [],
            "scatterData": [],
            "scatterXLabel": "EV/EBITDA",
            "scatterYLabel": "Revenue Growth",
            "loading": False,
        },
        "strategy": {
            "signal": None,
            "portfolio": None,
            "loading": False,
        },
        "memory": {
            "calibrationHits": 0,
            "calibrationMisses": 0,
            "recentRecalls": [],
            "loading": False,
        },
        "fundamentals": {
            "sections": [],
            "loading": False,
        },
    }


@dataclass
class AnalysisSession:
    id: str
    harness: Harness
    events: queue.Queue  # Queue[dict] — threading.Queue, NOT asyncio.Queue
    query: str = ""
    status: Literal["running", "waiting", "complete", "error", "idle"] = "running"
    turn_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_input_event: threading.Event = field(default_factory=threading.Event)
    user_input_response: str | None = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Accumulator state ─────────────────────────────────────
    accumulated_timeline: list = field(default_factory=list)
    _raw_text: str = ""  # All LLM text collected raw, parsed later in snapshot()
    accumulated_panels: dict = field(default_factory=dict)
    accumulated_frontend_panels: dict = field(default_factory=_default_frontend_panels)
    pending_valuation: dict | None = None

    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    # ── Accumulator ───────────────────────────────────────────

    def accumulate_raw(self, event: HarnessEvent) -> None:
        """
        Accumulate raw HarnessEvent data (untruncated).

        Handles TOOL_START, TOOL_END, and TEXT_DELTA events to build up
        timeline, reasoning/thinking text, and panel data.
        """
        if event.type == EventType.TOOL_START:
            self._handle_tool_start(event)
        elif event.type == EventType.TOOL_END:
            self._handle_tool_end(event)
        elif event.type == EventType.TEXT_DELTA:
            self._handle_text_delta(event)

    def _handle_tool_start(self, event: HarnessEvent) -> None:
        tool = event.data.get("tool", "")
        self.accumulated_timeline.append({
            "id": f"tool-{tool}-{uuid.uuid4().hex[:8]}",
            "tool": tool,
            "args": event.data.get("args"),
            "status": "running",
            "timestamp": time.time(),
        })

    def _handle_tool_end(self, event: HarnessEvent) -> None:
        tool = event.data.get("tool", "")
        status = event.data.get("status", "ok")
        # Prefer untruncated result_full over audit-truncated result
        result = event.data.get("result_full") or event.data.get("result")

        # Mark the last running timeline entry for this tool as complete
        for entry in reversed(self.accumulated_timeline):
            if entry["tool"] == tool and entry["status"] == "running":
                entry["status"] = "error" if status == "error" else "complete"
                break

        # Store full untruncated result
        if result is not None:
            self.accumulated_panels[tool] = result

        # Extract frontend-shaped panel data
        if result and isinstance(result, dict):
            if tool == "valuation":
                self._extract_valuation_panels(result)
            elif tool == "financials":
                self._extract_data_panel(result)
            elif tool == "quote":
                self._extract_quote_metrics(result)
            elif tool == "generate_trade_signal":
                self._extract_strategy_signal(result)
            elif tool == "execute_trade":
                self._extract_trade_execution(result)
            elif tool == "get_portfolio":
                self._extract_strategy_portfolio(result)
            elif tool in ("recall", "recall_memory"):
                self._extract_memory_recall(result)
            elif tool == "check_calibration":
                self._extract_memory_calibration(result)
            # Backward compatibility for old tool names
            elif tool == "build_dcf":
                self.pending_valuation = result
                self._extract_model_panel(result)
            elif tool == "get_comps":
                self._extract_comps_panel(result)
            elif tool == "fmp_get_financials":
                self._extract_data_panel(result)
            elif tool == "yf_quote":
                self._extract_quote_metrics(result)
            elif tool == "emit_research_section":
                self._extract_research_section(result)

    def _handle_text_delta(self, event: HarnessEvent) -> None:
        content = event.data.get("content", "")
        if content:
            self._raw_text += content

    def _extract_valuation_panels(self, result: dict) -> None:
        """Extract both model and comps panels from unified valuation result."""
        dcf = result.get("dcf")
        comps = result.get("comps")

        if isinstance(dcf, dict):
            self.pending_valuation = dcf
            self._extract_model_panel(dcf)
        elif result.get("fair_value_per_share") is not None:
            # If valuation tool flattened DCF outputs at top-level.
            self.pending_valuation = result
            self._extract_model_panel(result)

        if isinstance(comps, dict):
            self._extract_comps_panel(comps)
        elif isinstance(result.get("peers"), list):
            self._extract_comps_panel(result)

    # ── Panel extraction helpers ──────────────────────────────

    def _extract_model_panel(self, result: dict) -> None:
        """Extract model panel data from build_dcf result."""
        model = self.accumulated_frontend_panels["model"]

        fv = result.get("fair_value_per_share")
        cp = result.get("current_price")
        gap = result.get("gap_pct")
        if fv is not None:
            model["fairValue"] = {
                "fairValue": fv,
                "currentPrice": cp or 0,
                "currency": "USD",
                "upside": gap or 0,
                "confidence": "medium",
            }

        # Implied multiples
        mult = result.get("implied_multiples")
        if mult and isinstance(mult, dict):
            multiples = []
            if mult.get("fwd_pe") is not None:
                multiples.append({"label": "Fwd P/E", "value": f"{mult['fwd_pe']}x"})
            if mult.get("ev_ebitda") is not None:
                multiples.append({"label": "EV/EBITDA", "value": f"{mult['ev_ebitda']}x"})
            if mult.get("fcf_yield") is not None:
                multiples.append({"label": "FCF Yield", "value": f"{mult['fcf_yield'] * 100:.1f}%"})
            if mult.get("peg_ratio") is not None:
                multiples.append({"label": "PEG", "value": f"{mult['peg_ratio']}x"})
            if multiples:
                model["impliedMultiples"] = multiples

        # Sensitivity
        sens = result.get("sensitivity")
        if sens and isinstance(sens, dict):
            wacc_vals = sens.get("wacc_values", [])
            growth_vals = sens.get("growth_values", [])
            matrix = sens.get("matrix", [])
            row_vals = [f"{v * 100:.1f}%" for v in wacc_vals]
            col_vals = [f"{v * 100:.1f}%" for v in growth_vals]
            cells = []
            for i, row in enumerate(matrix):
                for j, val in enumerate(row if row else []):
                    if val is not None:
                        cells.append({
                            "row": row_vals[i] if i < len(row_vals) else "",
                            "col": col_vals[j] if j < len(col_vals) else "",
                            "value": val,
                            "isBase": (
                                i == len(wacc_vals) // 2
                                and j == len(growth_vals) // 2
                            ),
                        })
            if cells:
                model["sensitivityData"] = cells
                model["sensitivityRowValues"] = row_vals
                model["sensitivityColValues"] = col_vals

        # Year-by-year
        yby = result.get("year_by_year")
        if yby and isinstance(yby, list):
            projections = []
            for row in yby:
                revenue = row.get("revenue", 0)
                ebit = row.get("ebit", 0)
                projections.append({
                    "year": f"Y{row.get('year', '?')}",
                    "revenue": revenue,
                    "growth": row.get("revenue_growth", 0),
                    "ebitda": ebit,
                    "margin": (ebit / revenue * 100) if revenue else 0,
                    "fcf": row.get("fcf", 0),
                })
            if projections:
                model["yearByYear"] = projections

        model["loading"] = False

    def _extract_comps_panel(self, result: dict) -> None:
        """Extract comps panel data from get_comps result."""
        comps = self.accumulated_frontend_panels["comps"]
        raw_peers = result.get("peers", [])

        peers = []
        scatter = []
        for p in raw_peers:
            peers.append({
                "ticker": p.get("ticker", ""),
                "name": p.get("ticker", ""),
                "marketCap": p.get("market_cap", 0) or 0,
                "peRatio": p.get("fwd_pe", 0) or 0,
                "evEbitda": p.get("ev_ebitda", 0) or 0,
                "revenueGrowth": p.get("revenue_growth", 0) or 0,
                "margin": p.get("gross_margin", 0) or 0,
                "isTarget": p.get("is_target", False),
            })
            if p.get("ev_ebitda") is not None and p.get("revenue_growth") is not None:
                scatter.append({
                    "ticker": p.get("ticker", ""),
                    "x": p.get("ev_ebitda", 0) or 0,
                    "y": (p.get("revenue_growth", 0) or 0) * 100,
                    "isTarget": p.get("is_target", False),
                })

        if peers:
            comps["peers"] = peers
        if scatter:
            comps["scatterData"] = scatter
        comps["loading"] = False

    def _extract_data_panel(self, result: dict) -> None:
        """Extract data panel from fmp_get_financials result."""
        data_panel = self.accumulated_frontend_panels["data"]
        st_type = result.get("statement_type", "")
        raw_data = result.get("data", [])
        if not raw_data:
            return

        if st_type == "profile":
            p = raw_data[0] if raw_data else {}
            metrics = []
            if p.get("price"):
                metrics.append({"label": "Price", "value": p["price"], "unit": "USD"})
            if p.get("mktCap"):
                metrics.append({"label": "Market Cap", "value": f"{p['mktCap'] / 1e9:.1f}B", "unit": "USD"})
            if p.get("pe"):
                metrics.append({"label": "P/E", "value": f"{p['pe']:.1f}"})
            if p.get("beta"):
                metrics.append({"label": "Beta", "value": f"{p['beta']:.2f}"})
            if metrics:
                data_panel["metrics"].extend(metrics)
        else:
            # Financial statement — build a table
            titles = {
                "income-statement": "Income Statement",
                "balance-sheet-statement": "Balance Sheet",
                "cash-flow-statement": "Cash Flow",
                "ratios": "Ratios",
            }
            headers = [
                "Metric",
                *[
                    (r.get("calendarYear") or r.get("date", ""))[:4]
                    for r in raw_data
                ],
            ]

            key_fields: dict[str, list[str]] = {
                "income-statement": ["revenue", "grossProfit", "operatingIncome", "netIncome", "eps", "epsdiluted"],
                "balance-sheet-statement": ["totalAssets", "totalLiabilities", "totalEquity", "cashAndShortTermInvestments", "totalDebt"],
                "cash-flow-statement": ["operatingCashFlow", "capitalExpenditure", "freeCashFlow", "dividendsPaid"],
                "ratios": ["grossProfitMargin", "operatingProfitMargin", "netProfitMargin", "returnOnEquity", "debtEquityRatio"],
            }
            fields = key_fields.get(st_type)
            if not fields:
                latest = raw_data[0] if raw_data else {}
                fields = [k for k, v in latest.items() if isinstance(v, (int, float))][:8]

            rows = []
            for f in fields:
                values = []
                for r in raw_data:
                    v = r.get(f)
                    if v is None:
                        values.append("-")
                    elif isinstance(v, (int, float)):
                        if abs(v) >= 1e9:
                            values.append(f"{v / 1e9:.1f}B")
                        elif abs(v) >= 1e6:
                            values.append(f"{v / 1e6:.0f}M")
                        elif abs(v) < 1 and v != 0:
                            values.append(f"{v * 100:.1f}%")
                        else:
                            values.append(f"{v:.1f}")
                    else:
                        values.append(str(v))
                rows.append({"label": f, "values": values})

            ticker = result.get("ticker", "")
            table = {
                "title": f"{ticker} {titles.get(st_type, st_type)}",
                "headers": headers,
                "rows": rows,
            }
            data_panel["financialTables"].append(table)

        data_panel["loading"] = False

    def _extract_quote_metrics(self, result: dict) -> None:
        """Extract data panel metrics from yf_quote result."""
        data_panel = self.accumulated_frontend_panels["data"]
        ticker = result.get("ticker", "")
        metrics = []

        if result.get("price"):
            metrics.append({"label": f"{ticker} Price", "value": result["price"], "unit": result.get("currency", "USD")})
        if result.get("market_cap"):
            metrics.append({"label": "Market Cap", "value": f"${result['market_cap'] / 1e9:.1f}B"})
        if result.get("pe_trailing"):
            metrics.append({"label": "P/E (TTM)", "value": f"{result['pe_trailing']:.1f}"})
        if result.get("pe_forward"):
            metrics.append({"label": "Fwd P/E", "value": f"{result['pe_forward']:.1f}"})
        if result.get("ev_ebitda"):
            metrics.append({"label": "EV/EBITDA", "value": f"{result['ev_ebitda']:.1f}"})
        if result.get("dividend_yield"):
            metrics.append({"label": "Div Yield", "value": f"{result['dividend_yield'] * 100:.2f}%"})

        if metrics:
            data_panel["metrics"].extend(metrics)
        data_panel["loading"] = False

    def _extract_strategy_signal(self, result: dict) -> None:
        """Extract trading signal data for the strategy panel."""
        strategy = self.accumulated_frontend_panels["strategy"]
        strategy["signal"] = {
            "ticker": result.get("ticker", ""),
            "action": result.get("action", "WATCH"),
            "price": result.get("price", 0) or 0,
            "targetPrice": result.get("target_price", 0) or 0,
            "stopLoss": result.get("stop_loss", 0) or 0,
            "positionPct": result.get("position_pct", 0) or 0,
            "catalysts": result.get("catalysts", ""),
            "reasoning": result.get("reasoning", ""),
            "suggestedShares": result.get("suggested_shares", 0) or 0,
            "alreadyHeld": result.get("already_held", False),
        }
        strategy["loading"] = False

    def _extract_trade_execution(self, result: dict) -> None:
        """Extract trade execution result — refreshes portfolio view."""
        # After execution, the signal is consumed; clear it
        strategy = self.accumulated_frontend_panels["strategy"]
        strategy["signal"] = None
        strategy["loading"] = False

    def _extract_strategy_portfolio(self, result: dict) -> None:
        """Extract paper portfolio summary for the strategy panel."""
        strategy = self.accumulated_frontend_panels["strategy"]
        raw_positions = result.get("positions", []) or []
        positions = []
        for pos in raw_positions:
            positions.append({
                "ticker": pos.get("ticker", ""),
                "shares": pos.get("shares", 0) or 0,
                "avgCost": pos.get("avg_cost", 0) or 0,
                "livePrice": pos.get("live_price"),
                "marketValue": pos.get("market_value", 0) or 0,
                "unrealizedPnl": pos.get("unrealized_pnl", 0) or 0,
                "unrealizedPnlPct": pos.get("unrealized_pnl_pct", 0) or 0,
                "entryDate": pos.get("entry_date"),
            })

        strategy["portfolio"] = {
            "cash": result.get("cash", 0) or 0,
            "totalMarketValue": result.get("total_market_value", 0) or 0,
            "totalPortfolioValue": result.get("total_portfolio_value", 0) or 0,
            "totalUnrealizedPnl": result.get("total_unrealized_pnl", 0) or 0,
            "totalRealizedPnl": result.get("total_realized_pnl", 0) or 0,
            "totalReturnPct": result.get("total_return_pct", 0) or 0,
            "positionCount": result.get("position_count", len(positions)) or len(positions),
            "winLoss": result.get("win_loss", "—") or "—",
            "investedPct": result.get("invested_pct", 0) or 0,
            "positions": positions,
        }
        strategy["loading"] = False

    def _extract_memory_recall(self, result: dict) -> None:
        """Extract recall events so memory data survives into replay snapshots."""
        memory = self.accumulated_frontend_panels["memory"]
        if result.get("total_results") or result.get("content"):
            memory["recentRecalls"].append({
                "company": result.get("subject") or result.get("company") or "?",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "relevance": min(1, (result.get("total_results", 1) or 1) / 10),
            })
        memory["loading"] = False

    def _extract_memory_calibration(self, result: dict) -> None:
        """Extract calibration summary for replay snapshots."""
        memory = self.accumulated_frontend_panels["memory"]
        if result.get("hits") is not None:
            memory["calibrationHits"] = result.get("hits", 0) or 0
        if result.get("misses") is not None:
            memory["calibrationMisses"] = result.get("misses", 0) or 0
        memory["loading"] = False

    def _extract_research_section(self, result: dict) -> None:
        """Extract research section for the fundamentals panel."""
        fundamentals = self.accumulated_frontend_panels["fundamentals"]
        title = result.get("title", "")
        content = result.get("content", "")
        if title and content:
            fundamentals["sections"].append({
                "title": title,
                "content": content,
                "timestamp": time.time(),
            })
        fundamentals["loading"] = False

    # ── Text parsing ────────────────────────────────────────────

    @staticmethod
    def _split_thinking_blocks(raw: str) -> tuple[str, str, list[dict]]:
        """
        Parse <thinking>...</thinking> blocks from complete LLM text.

        Works on the full accumulated text — never on streaming fragments —
        so tags are always intact regardless of how they were chunked.

        Returns (reasoning, thinking, thinking_timeline_entries).
        """
        OPEN = "<thinking>"
        CLOSE = "</thinking>"
        reasoning_parts: list[str] = []
        thinking_parts: list[str] = []
        thinking_entries: list[dict] = []

        pos = 0
        while pos < len(raw):
            open_idx = raw.find(OPEN, pos)
            if open_idx == -1:
                reasoning_parts.append(raw[pos:])
                break

            # Text before the thinking block → reasoning
            reasoning_parts.append(raw[pos:open_idx])

            close_idx = raw.find(CLOSE, open_idx + len(OPEN))
            if close_idx == -1:
                # Unclosed block — treat the rest as thinking
                inside = raw[open_idx + len(OPEN):]
                thinking_parts.append(inside)
                thinking_entries.append({
                    "id": f"think-{uuid.uuid4().hex[:8]}",
                    "tool": "thinking",
                    "status": "complete",
                    "timestamp": time.time(),
                    "message": inside.strip().split("\n")[0][:80],
                    "fullText": inside.strip(),
                })
                break

            inside = raw[open_idx + len(OPEN):close_idx]
            thinking_parts.append(inside)
            thinking_entries.append({
                "id": f"think-{uuid.uuid4().hex[:8]}",
                "tool": "thinking",
                "status": "complete",
                "timestamp": time.time(),
                "message": inside.strip().split("\n")[0][:80],
                "fullText": inside.strip(),
            })
            pos = close_idx + len(CLOSE)

        return (
            "".join(reasoning_parts).strip(),
            "\n---\n".join(thinking_parts).strip(),
            thinking_entries,
        )

    # ── Snapshot ──────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Return a snapshot of accumulated data for persistence.

        Parses <thinking> blocks from the complete raw text — never from
        streaming fragments — so tag boundaries are always correct.
        """
        reasoning, thinking, thinking_entries = self._split_thinking_blocks(self._raw_text)

        # Merge thinking entries into the timeline, sorted chronologically
        timeline = list(self.accumulated_timeline) + thinking_entries
        timeline.sort(key=lambda e: e.get("timestamp", 0))

        return {
            "reasoning_text": reasoning,
            "thinking_text": thinking,
            "timeline": timeline,
            "panels": self.accumulated_frontend_panels,
        }


def create_session(harness: Harness, query: str = "") -> AnalysisSession:
    """Create a new analysis session wrapping a harness instance."""
    return AnalysisSession(
        id=uuid.uuid4().hex[:16],
        harness=harness,
        events=queue.Queue(),
        query=query,
    )


# Global session registry
_sessions: dict[str, AnalysisSession] = {}
_sessions_lock = threading.Lock()


def get_session(session_id: str) -> AnalysisSession | None:
    with _sessions_lock:
        return _sessions.get(session_id)


def register_session(session: AnalysisSession) -> None:
    with _sessions_lock:
        _sessions[session.id] = session


def remove_session(session_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)


def all_sessions() -> dict[str, AnalysisSession]:
    with _sessions_lock:
        return dict(_sessions)
