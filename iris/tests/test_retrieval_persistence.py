"""Tests for analysis_runs table and valuations ticker column (Task 1)."""
import json
import time

import pytest

from tools.retrieval import SQLiteRetriever


@pytest.fixture
def retriever(tmp_path):
    return SQLiteRetriever(str(tmp_path / "test.db"))


# ---- save_analysis_run + get_analysis_run round-trip ----

def test_save_and_get_analysis_run(retriever):
    retriever.save_analysis_run(
        id="run_001",
        query="Analyze NVDA",
        ticker="NVDA",
        status="completed",
        reasoning_text="Some reasoning",
        thinking_text="Some thinking",
        timeline_json='[{"step": 1}]',
        panels_json='[{"panel": "summary"}]',
        recommendation="BUY",
        tokens_in=100,
        tokens_out=200,
    )
    run = retriever.get_analysis_run("run_001")
    assert run is not None
    assert run["id"] == "run_001"
    assert run["query"] == "Analyze NVDA"
    assert run["ticker"] == "NVDA"
    assert run["status"] == "completed"
    assert run["reasoning_text"] == "Some reasoning"
    assert run["thinking_text"] == "Some thinking"
    assert run["timeline_json"] == '[{"step": 1}]'
    assert run["panels_json"] == '[{"panel": "summary"}]'
    assert run["recommendation"] == "BUY"
    assert run["tokens_in"] == 100
    assert run["tokens_out"] == 200
    assert run["created_at"] is not None


def test_get_analysis_run_nonexistent(retriever):
    result = retriever.get_analysis_run("nonexistent_id")
    assert result is None


# ---- list_analysis_runs ----

def test_list_analysis_runs_all(retriever):
    for i in range(5):
        retriever.save_analysis_run(
            id=f"run_{i:03d}",
            query=f"Query {i}",
            ticker="NVDA" if i % 2 == 0 else "AAPL",
            status="completed",
            reasoning_text="r",
            thinking_text="t",
            timeline_json="[]",
            panels_json="[]",
        )
    result = retriever.list_analysis_runs()
    assert result["total"] == 5
    assert len(result["items"]) == 5
    assert result["limit"] == 30
    assert result["offset"] == 0


def test_list_analysis_runs_filtered_by_ticker(retriever):
    for i in range(5):
        retriever.save_analysis_run(
            id=f"run_{i:03d}",
            query=f"Query {i}",
            ticker="NVDA" if i % 2 == 0 else "AAPL",
            status="completed",
            reasoning_text="r",
            thinking_text="t",
            timeline_json="[]",
            panels_json="[]",
        )
    result = retriever.list_analysis_runs(ticker="NVDA")
    assert result["total"] == 3  # indices 0, 2, 4
    assert all(item["ticker"] == "NVDA" for item in result["items"])


def test_list_analysis_runs_pagination(retriever):
    for i in range(10):
        retriever.save_analysis_run(
            id=f"run_{i:03d}",
            query=f"Query {i}",
            ticker="NVDA",
            status="completed",
            reasoning_text="r",
            thinking_text="t",
            timeline_json="[]",
            panels_json="[]",
        )
    page1 = retriever.list_analysis_runs(limit=3, offset=0)
    assert len(page1["items"]) == 3
    assert page1["total"] == 10

    page2 = retriever.list_analysis_runs(limit=3, offset=3)
    assert len(page2["items"]) == 3
    assert page2["offset"] == 3

    # No overlap
    ids_1 = {item["id"] for item in page1["items"]}
    ids_2 = {item["id"] for item in page2["items"]}
    assert ids_1.isdisjoint(ids_2)


# ---- get_latest_run_for_ticker ----

def test_get_latest_run_for_ticker(retriever):
    retriever.save_analysis_run(
        id="run_old",
        query="Old query",
        ticker="NVDA",
        status="completed",
        reasoning_text="old",
        thinking_text="old",
        timeline_json="[]",
        panels_json="[]",
    )
    retriever.save_analysis_run(
        id="run_new",
        query="New query",
        ticker="NVDA",
        status="completed",
        reasoning_text="new",
        thinking_text="new",
        timeline_json="[]",
        panels_json="[]",
    )
    latest = retriever.get_latest_run_for_ticker("NVDA")
    assert latest is not None
    assert latest["id"] == "run_new"
    assert latest["reasoning_text"] == "new"


def test_get_latest_run_for_ticker_none(retriever):
    result = retriever.get_latest_run_for_ticker("AAPL")
    assert result is None


# ---- save_valuation_record + get_latest_valuation ----

def test_save_valuation_record_and_get_latest(retriever):
    retriever.save_valuation_record(
        ticker="NVDA",
        fair_value=150.0,
        current_price=120.0,
        gap_pct=25.0,
        run_id="run_001",
    )
    val = retriever.get_latest_valuation("NVDA")
    assert val is not None
    assert val["ticker"] == "NVDA"
    data = json.loads(val["data"]) if isinstance(val["data"], str) else val["data"]
    assert data["fair_value"] == 150.0
    assert data["current_price"] == 120.0
    assert data["gap_pct"] == 25.0
    assert data["run_id"] == "run_001"


def test_get_latest_valuation_returns_newest(retriever):
    retriever.save_valuation_record(
        ticker="NVDA",
        fair_value=100.0,
        current_price=90.0,
        gap_pct=11.1,
        run_id="run_001",
    )
    retriever.save_valuation_record(
        ticker="NVDA",
        fair_value=200.0,
        current_price=180.0,
        gap_pct=11.1,
        run_id="run_002",
    )
    val = retriever.get_latest_valuation("NVDA")
    assert val is not None
    data = json.loads(val["data"]) if isinstance(val["data"], str) else val["data"]
    assert data["fair_value"] == 200.0
    assert data["run_id"] == "run_002"


def test_get_latest_valuation_nonexistent(retriever):
    result = retriever.get_latest_valuation("ZZZZZ")
    assert result is None


# ---- get_tracked_tickers ----

def test_get_tracked_tickers(retriever):
    for ticker in ["NVDA", "nvda", "AAPL", "MSFT"]:
        retriever.save_analysis_run(
            id=f"run_{ticker}",
            query=f"Analyze {ticker}",
            ticker=ticker,
            status="completed",
            reasoning_text="r",
            thinking_text="t",
            timeline_json="[]",
            panels_json="[]",
        )
    tickers = retriever.get_tracked_tickers()
    assert set(tickers) == {"NVDA", "AAPL", "MSFT"}


def test_get_tracked_tickers_empty(retriever):
    tickers = retriever.get_tracked_tickers()
    assert tickers == []
