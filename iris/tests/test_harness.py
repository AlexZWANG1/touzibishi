import json
import threading
import time
from unittest.mock import MagicMock, patch
from llm.base import LLMResponse, ToolCall
from core.harness import Harness, HarnessConfig, HarnessEvent, EventType
from tools.base import ToolResult


def make_mock_llm(responses: list[LLMResponse]):
    mock = MagicMock()
    mock.chat.side_effect = responses
    return mock


def test_harness_stops_when_no_tool_calls():
    mock_llm = make_mock_llm([
        LLMResponse(content="Analysis complete: WATCH recommendation.", tool_calls=[])
    ])
    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5),
    )
    result = harness.run("Analyze NVDA")
    assert result.ok
    assert "WATCH" in result.reply


def test_harness_rejects_unknown_tool():
    """Unknown tools return a structured not-found error."""
    tool_call = ToolCall(
        id="tc_001", name="does_not_exist", arguments={}
    )
    mock_llm = make_mock_llm([
        LLMResponse(content=None, tool_calls=[tool_call]),
        LLMResponse(content="Unknown tool handled.", tool_calls=[]),
    ])
    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5),
    )
    harness.run("Analyze NVDA")
    second_call_messages = mock_llm.chat.call_args_list[1][0][0]
    tool_result_msg = next(m for m in second_call_messages if m["role"] == "tool")
    content = json.loads(tool_result_msg["content"])
    assert content["status"] == "error"
    assert "not found" in content["error"].lower()


def test_harness_exhausts_rounds():
    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"results": [], "sources": []}))

    infinite = [
        LLMResponse(content=None, tool_calls=[
            ToolCall(id=f"tc_{i}", name="exa_search", arguments={"query": "NVDA"})
        ])
        for i in range(10)
    ]
    mock_llm = make_mock_llm(infinite)
    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=3),
    )
    result = harness.run("Analyze NVDA")
    assert not result.ok
    assert "MAX_TOOL_ROUNDS" in result.error


def test_harness_stops_on_total_tool_budget():
    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"results": [], "sources": []}))

    responses = [
        LLMResponse(content=None, tool_calls=[
            ToolCall(id=f"tc_{i}", name="exa_search", arguments={"query": "NVDA"})
        ])
        for i in range(10)
    ]
    mock_llm = make_mock_llm(responses)
    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=10, max_total_tool_calls=2),
    )
    result = harness.run("Analyze NVDA")
    assert not result.ok
    assert "MAX_TOTAL_TOOL_CALLS" in result.error


def test_harness_parallel_tool_execution():
    """Multiple tool calls in one response are dispatched in parallel."""
    tool_a = MagicMock()
    tool_a.name = "exa_search"
    tool_a.schema = {"type": "function", "function": {"name": "exa_search"}}
    tool_a.execute = MagicMock(return_value=ToolResult.ok({"results": []}))

    tool_b = MagicMock()
    tool_b.name = "web_fetch"
    tool_b.schema = {"type": "function", "function": {"name": "web_fetch"}}
    tool_b.execute = MagicMock(return_value=ToolResult.ok({"content": "page"}))

    mock_llm = make_mock_llm([
        LLMResponse(content=None, tool_calls=[
            ToolCall(id="tc_1", name="exa_search", arguments={"query": "NVDA"}),
            ToolCall(id="tc_2", name="web_fetch", arguments={"url": "https://example.com"}),
        ]),
        LLMResponse(content="Done.", tool_calls=[]),
    ])

    harness = Harness(
        llm=mock_llm, tools=[tool_a, tool_b], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5, parallel_tool_execution=True),
    )
    result = harness.run("Analyze NVDA")
    assert result.ok
    assert tool_a.execute.called
    assert tool_b.execute.called


def test_harness_retry_on_rate_limit():
    """Harness retries on rate limit errors with backoff."""
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        Exception("rate_limit_error: too many requests"),
        LLMResponse(content="Done after retry.", tool_calls=[]),
    ]

    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5, max_retries=3, retry_base_delay=0.01),
    )
    result = harness.run("Analyze NVDA")
    assert result.ok
    assert "retry" in result.reply.lower() or result.reply == "Done after retry."
    assert mock_llm.chat.call_count == 2


def test_harness_abort():
    """Abort cancels the run."""
    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}

    # Tool execution sleeps, giving abort time to fire
    def slow_execute(args):
        time.sleep(0.1)
        return ToolResult.ok({"results": []})

    mock_tool.execute = slow_execute

    # Provide many rounds of tool calls so the loop keeps going
    responses = [
        LLMResponse(content=None, tool_calls=[
            ToolCall(id=f"tc_{i}", name="exa_search", arguments={"query": "NVDA"})
        ])
        for i in range(10)
    ]
    mock_llm = make_mock_llm(responses)

    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=10),
    )

    # Abort after tool starts executing
    def abort_soon():
        time.sleep(0.15)
        harness.abort()

    t = threading.Thread(target=abort_soon)
    t.start()
    result = harness.run("Analyze NVDA")
    t.join()

    assert not result.ok
    assert "abort" in result.error.lower()


def test_harness_steering():
    """Steering messages are injected between rounds."""
    events = []

    def collect_events(e: HarnessEvent):
        events.append(e)

    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"results": []}))

    mock_llm = make_mock_llm([
        LLMResponse(content=None, tool_calls=[
            ToolCall(id="tc_1", name="exa_search", arguments={"query": "NVDA"})
        ]),
        LLMResponse(content="Adjusted analysis.", tool_calls=[]),
    ])

    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5),
        on_event=collect_events,
    )

    # Pre-load a steering message
    harness.steer("Focus on data center revenue instead")

    result = harness.run("Analyze NVDA")
    assert result.ok

    # Check steering message was injected
    steering_events = [e for e in events if e.type == EventType.STEERING_INJECTED]
    assert len(steering_events) >= 1


def test_harness_context_compaction():
    """Large tool results trigger context compaction."""
    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}
    # Return a very large result
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"content": "x" * 10000}))

    # The LLM now gets called for: (1) initial run, (2) summary during compaction, (3) continuation
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        LLMResponse(content=None, tool_calls=[
            ToolCall(id="tc_1", name="exa_search", arguments={"query": "NVDA"})
        ]),
        # Summary call from _llm_summarize during compaction
        LLMResponse(content="Summary of earlier context.", tool_calls=[]),
        LLMResponse(content="Done.", tool_calls=[]),
    ]

    events = []
    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(
            max_tool_rounds=5,
            context_limit_chars=500,  # Very low to trigger compaction
            compress_threshold_chars=100,
        ),
        on_event=lambda e: events.append(e),
    )
    result = harness.run("Analyze NVDA")
    # Should still complete (compaction recovers)
    assert result.ok or any(e.type == EventType.CONTEXT_COMPACTED for e in events)


def test_harness_events_emitted():
    """Events are emitted for turn start/end and tool start/end."""
    events = []

    mock_tool = MagicMock()
    mock_tool.name = "exa_search"
    mock_tool.schema = {"type": "function", "function": {"name": "exa_search"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"results": []}))

    mock_llm = make_mock_llm([
        LLMResponse(content=None, tool_calls=[
            ToolCall(id="tc_1", name="exa_search", arguments={"query": "NVDA"})
        ]),
        LLMResponse(content="Done.", tool_calls=[]),
    ])

    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5),
        on_event=lambda e: events.append(e),
    )
    harness.run("Analyze NVDA")

    event_types = [e.type for e in events]
    assert EventType.TURN_START in event_types
    assert EventType.TOOL_START in event_types
    assert EventType.TOOL_END in event_types
    assert EventType.TURN_END in event_types


def test_dynamic_tool_injection_limits_exposed_tools():
    """Dynamic mode should expose at most max_tools_per_round schemas."""
    tool_a = MagicMock()
    tool_a.name = "exa_search"
    tool_a.schema = {
        "type": "function",
        "function": {
            "name": "exa_search",
            "description": "semantic search for financial news",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
        },
    }
    tool_b = MagicMock()
    tool_b.name = "fred_get_macro"
    tool_b.schema = {
        "type": "function",
        "function": {
            "name": "fred_get_macro",
            "description": "get macro CPI and FEDFUNDS series",
            "parameters": {"type": "object", "properties": {"series_id": {"type": "string"}}},
        },
    }
    tool_c = MagicMock()
    tool_c.name = "run_valuation"
    tool_c.schema = {
        "type": "function",
        "function": {
            "name": "run_valuation",
            "description": "run valuation model",
            "parameters": {"type": "object", "properties": {"hypothesis_id": {"type": "string"}}},
        },
    }

    harness = Harness(
        llm=MagicMock(),
        tools=[tool_a, tool_b, tool_c],
        soul="You are IRIS.",
        config=HarnessConfig(tool_injection_mode="dynamic", max_tools_per_round=2),
    )
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "Need macro CPI FEDFUNDS trend for the view"},
    ]
    schemas = harness._tool_schemas(messages, recent_tool_names=[])
    assert len(schemas) == 2
    names = [s["function"]["name"] for s in schemas]
    assert "fred_get_macro" in names


# ── Task 6: LLM-based Context Compaction ─────────────────────

def test_llm_compaction_calls_summarizer():
    summary_response = LLMResponse(
        content="## Summary\nNVDA revenue up 78%. Hypothesis created with 50% confidence.",
        tool_calls=[],
    )
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [summary_response]

    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5, context_limit_chars=200),
    )

    messages = [
        {"role": "system", "content": "You are IRIS."},
        {"role": "user", "content": "Analyze NVDA"},
    ]
    for i in range(10):
        messages.append({"role": "assistant", "content": f"Step {i}: " + "x" * 50})
        messages.append({"role": "user", "content": f"Continue {i}"})

    harness._compact_context(messages)
    assert mock_llm.chat.call_count >= 1
    assert len(messages) < 22
    summary_msgs = [m for m in messages if "CONTEXT SUMMARY" in m.get("content", "")]
    assert len(summary_msgs) >= 1


# ── Task 7: Cross-session Context Loading ─────────────────────

def test_cross_session_context_loading():
    from tools.retrieval import SQLiteRetriever
    from tools.knowledge import extract_observation, create_hypothesis
    import tempfile, os

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = os.path.join(tmp, "test.db")
        retriever = SQLiteRetriever(db_path)
        extract_observation(
            retriever=retriever, subject="NVDA",
            claim="Revenue up 78%", source="Earnings",
            fact_or_view="fact", relevance=0.9,
            citation="...", time_str="2026-02-21", extracted_by="test",
        )
        create_hypothesis(
            retriever=retriever, company="NVDA",
            thesis="AI dominance", timeframe="24m",
            drivers=[
                {"name": "d1", "description": "x", "current_assessment": "ok"},
                {"name": "d2", "description": "y", "current_assessment": "ok"},
                {"name": "d3", "description": "z", "current_assessment": "ok"},
            ],
            kill_criteria=[{"description": "k1"}],
            initial_confidence=60.0,
        )

        mock_llm = make_mock_llm([
            LLMResponse(content="Analysis with prior context.", tool_calls=[]),
        ])
        harness = Harness(
            llm=mock_llm, tools=[], soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5),
            retriever=retriever,
        )
        result = harness.run("Continue analyzing NVDA")
        assert result.ok
        call_messages = mock_llm.chat.call_args_list[0][0][0]
        user_msg = call_messages[1]["content"]
        assert "Revenue up 78%" in user_msg or "Prior Analysis" in user_msg
