import json
from unittest.mock import MagicMock
from llm.base import LLMResponse, ToolCall
from core.harness import Harness, HarnessConfig
from guards.guards import InvestmentGuards
from core.invariants import InvariantChecker
from tools.retrieval import SQLiteRetriever
from tools.base import ToolResult


def make_mock_llm(responses: list[LLMResponse]):
    mock = MagicMock()
    mock.chat.side_effect = responses
    return mock


def test_harness_stops_when_no_tool_calls(tmp_path):
    mock_llm = make_mock_llm([
        LLMResponse(content="Analysis complete: WATCH recommendation.", tool_calls=[])
    ])
    retriever = SQLiteRetriever(str(tmp_path / "test.db"))
    harness = Harness(
        llm=mock_llm, tools=[], guards=InvestmentGuards(),
        invariants=InvariantChecker(), retriever=retriever,
        soul="You are IRIS.", config=HarnessConfig(max_tool_rounds=5),
    )
    result = harness.run("Analyze NVDA")
    assert result.ok
    assert "WATCH" in result.reply


def test_harness_blocks_guard_violation(tmp_path):
    tool_call_bad = ToolCall(
        id="tc_001", name="run_valuation",
        arguments={
            "wacc": 0.99, "terminal_growth_rate": 0.02, "reasoning": "test",
            "hypothesis_id": "hyp_001", "methodology": "DCF",
            "methodology_reasoning": "test", "fair_value_low": 100.0,
            "fair_value_high": 130.0, "current_price": 90.0,
            "key_assumptions": [], "bull_case_value": 130.0,
            "bull_case_assumption": "high", "bear_case_value": 100.0,
            "bear_case_assumption": "low",
        }
    )
    mock_llm = make_mock_llm([
        LLMResponse(content=None, tool_calls=[tool_call_bad]),
        LLMResponse(content="Cannot complete valuation with invalid WACC.", tool_calls=[]),
    ])
    retriever = SQLiteRetriever(str(tmp_path / "test.db"))
    harness = Harness(
        llm=mock_llm, tools=[], guards=InvestmentGuards(),
        invariants=InvariantChecker(), retriever=retriever,
        soul="You are IRIS.", config=HarnessConfig(max_tool_rounds=5),
    )
    harness.run("Analyze NVDA")
    second_call_messages = mock_llm.chat.call_args_list[1][0][0]
    tool_result_msg = next(m for m in second_call_messages if m["role"] == "tool")
    content = json.loads(tool_result_msg["content"])
    assert content["status"] == "error"
    assert "WACC" in content["error"]


def test_harness_exhausts_rounds(tmp_path):
    mock_tool = MagicMock()
    mock_tool.name = "perplexity_search"
    mock_tool.schema = {"type": "function", "function": {"name": "perplexity_search"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"summary": "test", "sources": []}))

    infinite = [
        LLMResponse(content=None, tool_calls=[
            ToolCall(id=f"tc_{i}", name="perplexity_search", arguments={"query": "NVDA"})
        ])
        for i in range(10)
    ]
    mock_llm = make_mock_llm(infinite)
    retriever = SQLiteRetriever(str(tmp_path / "test.db"))
    harness = Harness(
        llm=mock_llm, tools=[mock_tool], guards=InvestmentGuards(),
        invariants=InvariantChecker(), retriever=retriever,
        soul="You are IRIS.", config=HarnessConfig(max_tool_rounds=3),
    )
    result = harness.run("Analyze NVDA")
    assert not result.ok
    assert "MAX_TOOL_ROUNDS" in result.error
