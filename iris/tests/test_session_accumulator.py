"""
Tests for AnalysisSession.accumulate_raw() — server-side data collection.

Covers: timeline accumulation, reasoning/thinking text parsing,
panel data extraction (build_dcf, get_comps, fmp_get_financials, yf_quote),
and the snapshot() method.
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project root is on sys.path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.harness import EventType, HarnessEvent
from backend.sessions import AnalysisSession, create_session


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def session():
    """Create a fresh AnalysisSession with a mocked harness."""
    harness = MagicMock()
    return create_session(harness)


# ── Tool timeline tests ──────────────────────────────────────


class TestToolTimeline:
    def test_tool_start_creates_running_timeline_entry(self, session):
        event = HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "fmp_get_financials", "args": {"ticker": "AAPL"}},
        )
        session.accumulate_raw(event)

        assert len(session.accumulated_timeline) == 1
        entry = session.accumulated_timeline[0]
        assert entry["tool"] == "fmp_get_financials"
        assert entry["status"] == "running"
        assert "timestamp" in entry

    def test_tool_end_marks_complete_and_stores_full_result(self, session):
        # First, start the tool
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "fmp_get_financials", "args": {"ticker": "AAPL"}},
        ))

        # Create a large result that would be truncated in SSE (>10KB)
        large_data = {"data": [{"field": "x" * 2000} for _ in range(10)]}
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "fmp_get_financials", "status": "ok", "result": large_data},
        ))

        # Timeline entry should be marked complete
        assert session.accumulated_timeline[0]["status"] == "complete"

        # Full untruncated result should be stored in accumulated_panels
        assert "fmp_get_financials" in session.accumulated_panels
        stored = session.accumulated_panels["fmp_get_financials"]
        assert stored == large_data  # Not truncated

    def test_tool_end_error_status(self, session):
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "build_dcf", "args": {}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "build_dcf", "status": "error", "result": {"error": "failed"}},
        ))

        assert session.accumulated_timeline[0]["status"] == "error"


# ── Text delta / reasoning tests ─────────────────────────────


class TestTextDelta:
    def test_accumulates_reasoning_text(self, session):
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "Apple's revenue grew "},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "by 15% year-over-year."},
        ))

        snap = session.snapshot()
        assert snap["reasoning_text"] == "Apple's revenue grew by 15% year-over-year."

    def test_accumulates_thinking_blocks(self, session):
        """Thinking blocks split from reasoning even when tags span chunks."""
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "Before thinking. <thinking>I need to analyze"},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": " the revenue trends carefully."},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "</thinking>After thinking."},
        ))

        snap = session.snapshot()
        assert "Before thinking." in snap["reasoning_text"]
        assert "After thinking." in snap["reasoning_text"]
        assert "<thinking>" not in snap["reasoning_text"]
        assert "I need to analyze the revenue trends carefully." in snap["thinking_text"]

    def test_thinking_block_creates_timeline_entry(self, session):
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "<thinking>Deep analysis here.</thinking>"},
        ))

        snap = session.snapshot()
        thinking_entries = [
            e for e in snap["timeline"] if e.get("tool") == "thinking"
        ]
        assert len(thinking_entries) == 1
        assert "Deep analysis here." in thinking_entries[0]["fullText"]

    def test_thinking_tags_split_across_chunks(self, session):
        """The real streaming scenario: tags split across token boundaries."""
        # Simulate: "<th" + "inking" + ">" + "内容" + "</thi" + "nking>"
        for chunk in ["<th", "inking", ">\n分析 NVDA", "\n准备构建 DCF", "</thi", "nking>", "结论"]:
            session.accumulate_raw(HarnessEvent(
                type=EventType.TEXT_DELTA,
                data={"content": chunk},
            ))

        snap = session.snapshot()
        assert "<thinking>" not in snap["reasoning_text"]
        assert "</thinking>" not in snap["reasoning_text"]
        assert "结论" in snap["reasoning_text"]
        assert "分析 NVDA" in snap["thinking_text"]
        assert "准备构建 DCF" in snap["thinking_text"]

        thinking_entries = [e for e in snap["timeline"] if e.get("tool") == "thinking"]
        assert len(thinking_entries) == 1

    def test_multiple_thinking_blocks(self, session):
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "A<thinking>first</thinking>B<thinking>second</thinking>C"},
        ))

        snap = session.snapshot()
        assert snap["reasoning_text"] == "ABC"
        assert "first" in snap["thinking_text"]
        assert "second" in snap["thinking_text"]
        thinking_entries = [e for e in snap["timeline"] if e.get("tool") == "thinking"]
        assert len(thinking_entries) == 2


# ── Panel extraction tests ───────────────────────────────────


class TestPanelExtraction:
    def test_build_dcf_extracts_pending_valuation(self, session):
        dcf_result = {
            "fair_value_per_share": 185.50,
            "current_price": 170.00,
            "gap_pct": 9.12,
            "year_by_year": [
                {"year": 1, "revenue": 400e9, "ebit": 120e9, "fcf": 100e9},
                {"year": 2, "revenue": 440e9, "ebit": 132e9, "fcf": 110e9},
            ],
            "sensitivity": {
                "wacc_values": [0.08, 0.09, 0.10],
                "growth_values": [0.02, 0.025, 0.03],
                "matrix": [[200, 190, 180], [185, 175, 165], [170, 160, 150]],
            },
            "implied_multiples": {
                "fwd_pe": 22.5,
                "ev_ebitda": 15.3,
                "fcf_yield": 0.045,
                "peg_ratio": 1.8,
            },
        }

        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "build_dcf", "args": {}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "build_dcf", "status": "ok", "result": dcf_result},
        ))

        # pending_valuation should be extracted
        assert session.pending_valuation is not None
        assert session.pending_valuation["fair_value_per_share"] == 185.50
        assert session.pending_valuation["current_price"] == 170.00

        # Model panel should be populated
        model = session.accumulated_frontend_panels["model"]
        assert model["fairValue"] is not None
        assert model["fairValue"]["fairValue"] == 185.50
        assert len(model["impliedMultiples"]) > 0
        assert len(model["sensitivityData"]) > 0
        assert len(model["yearByYear"]) == 2

    def test_get_comps_extracts_comps_panel(self, session):
        comps_result = {
            "target": "AAPL",
            "peers": [
                {"ticker": "MSFT", "fwd_pe": 30.0, "ev_ebitda": 22.0, "revenue_growth": 0.12, "gross_margin": 0.68, "is_target": False},
                {"ticker": "AAPL", "fwd_pe": 28.0, "ev_ebitda": 20.0, "revenue_growth": 0.08, "gross_margin": 0.45, "is_target": True},
            ],
        }

        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "get_comps", "args": {}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "get_comps", "status": "ok", "result": comps_result},
        ))

        comps = session.accumulated_frontend_panels["comps"]
        assert len(comps["peers"]) == 2
        assert comps["peers"][0]["ticker"] == "MSFT"
        assert len(comps["scatterData"]) == 2

    def test_fmp_get_financials_extracts_data_panel(self, session):
        fin_result = {
            "ticker": "AAPL",
            "statement_type": "income-statement",
            "period": "annual",
            "data": [
                {"calendarYear": "2024", "revenue": 380e9, "grossProfit": 170e9, "operatingIncome": 115e9, "netIncome": 95e9, "eps": 6.2, "epsdiluted": 6.1},
                {"calendarYear": "2023", "revenue": 365e9, "grossProfit": 160e9, "operatingIncome": 110e9, "netIncome": 90e9, "eps": 5.9, "epsdiluted": 5.8},
            ],
        }

        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "fmp_get_financials", "args": {"ticker": "AAPL"}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "fmp_get_financials", "status": "ok", "result": fin_result},
        ))

        data = session.accumulated_frontend_panels["data"]
        assert len(data["financialTables"]) == 1
        table = data["financialTables"][0]
        assert "AAPL" in table["title"]
        assert len(table["rows"]) > 0

    def test_yf_quote_extracts_metrics(self, session):
        quote_result = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "price": 175.50,
            "market_cap": 2.8e12,
            "pe_trailing": 28.5,
            "pe_forward": 26.0,
            "ev_ebitda": 22.0,
            "dividend_yield": 0.005,
            "currency": "USD",
        }

        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "yf_quote", "args": {"ticker": "AAPL"}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "yf_quote", "status": "ok", "result": quote_result},
        ))

        data = session.accumulated_frontend_panels["data"]
        assert len(data["metrics"]) > 0
        labels = [m["label"] for m in data["metrics"]]
        assert any("AAPL" in l for l in labels)


# ── Snapshot test ────────────────────────────────────────────


class TestSnapshot:
    def test_snapshot_returns_complete_data(self, session):
        # Accumulate some data
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "Analysis reasoning text."},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TEXT_DELTA,
            data={"content": "<thinking>Internal thoughts.</thinking>"},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_START,
            data={"tool": "exa_search", "args": {"query": "AAPL"}},
        ))
        session.accumulate_raw(HarnessEvent(
            type=EventType.TOOL_END,
            data={"tool": "exa_search", "status": "ok", "result": {"results": []}},
        ))

        snap = session.snapshot()

        assert "reasoning_text" in snap
        assert "thinking_text" in snap
        assert "timeline" in snap
        assert "panels" in snap
        assert snap["reasoning_text"] == "Analysis reasoning text."
        assert "Internal thoughts." in snap["thinking_text"]
        assert len(snap["timeline"]) >= 1  # at least tool + thinking entries
        assert "data" in snap["panels"]
        assert "model" in snap["panels"]
        assert "comps" in snap["panels"]
        assert "memory" in snap["panels"]
