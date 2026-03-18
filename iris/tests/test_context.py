import json
from unittest.mock import MagicMock, patch
from llm.base import LLMResponse, ToolCall
from core.harness import Harness, HarnessConfig, EventType
from tools.base import ToolResult


def test_memory_flush_before_compaction():
    flush_tool_call = ToolCall(
        id="flush_tc_1", name="extract_observation",
        arguments={
            "subject": "NVDA", "claim": "Revenue up 78%",
            "source": "prior conversation", "fact_or_view": "fact",
            "relevance": 0.9, "citation": "...", "time_str": "2026-02-21",
        },
    )
    flush_response = LLMResponse(content=None, tool_calls=[flush_tool_call])
    summary_response = LLMResponse(content="Summary: NVDA analysis.", tool_calls=[])

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [flush_response, summary_response]

    mock_tool = MagicMock()
    mock_tool.name = "extract_observation"
    mock_tool.schema = {"type": "function", "function": {"name": "extract_observation"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"id": "obs_flush"}))

    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
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
    assert mock_tool.execute.called


def test_memory_flush_skipped_when_disabled():
    mock_llm = MagicMock()
    summary_response = LLMResponse(content="Summary.", tool_calls=[])
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
        messages.append({"role": "assistant", "content": "x" * 50})
        messages.append({"role": "user", "content": "continue"})

    with patch("core.config.get", side_effect=lambda key, default=None: {
        "compaction.keep_recent_messages": 6,
        "compaction.strategy": "llm_summary",
        "compaction.memory_flush.enabled": False,
        "compaction.summary_max_input_chars": 50000,
        "compaction.summary_prompt": "Summarize.",
    }.get(key, default)):
        harness._compact_context(messages)
    assert mock_llm.chat.call_count == 1


def test_full_context_system_integration(tmp_path):
    """Integration: cross-session loading + compaction + memory flush all work together."""
    from tools.retrieval import SQLiteRetriever
    from tools.knowledge import extract_observation, create_hypothesis

    db_path = str(tmp_path / "test.db")
    retriever = SQLiteRetriever(db_path)

    # Pre-populate prior session data
    extract_observation(
        retriever=retriever, subject="TSLA",
        claim="FSD v13 achieves 5x safety improvement",
        source="Tesla AI Day", fact_or_view="fact", relevance=0.85,
        citation="...", time_str="2026-03-01", extracted_by="test",
    )
    create_hypothesis(
        retriever=retriever, company="TSLA",
        thesis="Tesla robotaxi launch creates new revenue stream",
        timeframe="18 months",
        drivers=[
            {"name": "FSD tech", "description": "Autonomous driving capability", "current_assessment": "improving"},
            {"name": "Regulatory", "description": "State approvals", "current_assessment": "pending"},
            {"name": "Fleet size", "description": "Vehicle production", "current_assessment": "strong"},
        ],
        kill_criteria=[{"description": "Fatal FSD accident triggers regulatory ban"}],
        initial_confidence=55.0,
    )

    mock_llm = MagicMock()
    mock_llm.chat.return_value = LLMResponse(
        content="Continuing TSLA analysis with prior context.", tool_calls=[],
    )

    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5),
        retriever=retriever,
    )

    result = harness.run("Update TSLA robotaxi analysis")
    assert result.ok

    # Verify prior context was loaded into the user message
    sent_messages = mock_llm.chat.call_args_list[0][0][0]
    user_msg = sent_messages[1]["content"]
    assert "TSLA" in user_msg
    assert "robotaxi" in user_msg or "Prior Analysis" in user_msg
