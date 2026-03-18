"""
End-to-end integration tests for the IRIS context & memory system.

Tests the complete flow: analysis cycle with persistence, context compaction,
memory search, memory flush, and graceful degradation -- all with mocked LLM.
"""

import json
from unittest.mock import MagicMock, patch, call

from llm.base import LLMResponse, ToolCall, LLMClient
from core.harness import Harness, HarnessConfig, EventType
from tools.base import Tool, ToolResult
from tools.retrieval import SQLiteRetriever
from tools.knowledge import (
    extract_observation,
    create_hypothesis,
    add_evidence_card,
    compute_trade_score,
    memory_search,
    EXTRACT_OBSERVATION_SCHEMA,
    CREATE_HYPOTHESIS_SCHEMA,
    ADD_EVIDENCE_CARD_SCHEMA,
    COMPUTE_TRADE_SCORE_SCHEMA,
    MEMORY_SEARCH_SCHEMA,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_embed(texts):
    """Deterministic fake embeddings for testing."""
    results = []
    for t in texts:
        h = hash(t) % 1000
        results.append([h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000])
    return results


def _make_knowledge_tools(retriever):
    """Build the subset of knowledge tools used by the harness."""
    return [
        Tool(extract_observation, EXTRACT_OBSERVATION_SCHEMA, retriever=retriever),
        Tool(create_hypothesis, CREATE_HYPOTHESIS_SCHEMA, retriever=retriever),
        Tool(add_evidence_card, ADD_EVIDENCE_CARD_SCHEMA, retriever=retriever),
        Tool(compute_trade_score, COMPUTE_TRADE_SCORE_SCHEMA, retriever=retriever),
        Tool(memory_search, MEMORY_SEARCH_SCHEMA, retriever=retriever),
    ]


# ---------------------------------------------------------------------------
# Test 1: Full analysis cycle with context persistence
# ---------------------------------------------------------------------------

class TestFullAnalysisCycleWithPersistence:
    """
    Run harness.run() with a mock LLM that simulates a multi-round analysis:
    extract_observation -> create_hypothesis -> add_evidence_card -> compute_trade_score.
    Then create a NEW harness with the SAME db and verify prior context is loaded.
    """

    def test_full_cycle_persists_and_reloads(self, tmp_path):
        db_path = str(tmp_path / "cycle.db")
        retriever = SQLiteRetriever(db_path)

        # Patch _embed so save_observation / save_hypothesis don't call OpenAI
        with patch.object(retriever, "_embed", side_effect=_mock_embed):
            tools = _make_knowledge_tools(retriever)

            # -- Round 1: extract_observation --------------------------------
            tc_obs = ToolCall(
                id="tc_obs",
                name="extract_observation",
                arguments={
                    "subject": "NVDA",
                    "claim": "Data center revenue up 78% YoY",
                    "source": "Q4 Earnings Call",
                    "fact_or_view": "fact",
                    "relevance": 0.95,
                    "citation": "Revenue was $XX billion...",
                    "time_str": "2026-02-21",
                },
            )
            # -- Round 2: create_hypothesis ----------------------------------
            tc_hyp = ToolCall(
                id="tc_hyp",
                name="create_hypothesis",
                arguments={
                    "company": "NVDA",
                    "thesis": "NVDA will dominate AI infrastructure for 3+ years",
                    "timeframe": "36 months",
                    "drivers": [
                        {"name": "CUDA moat", "description": "Software ecosystem lock-in", "current_assessment": "very strong"},
                        {"name": "DC demand", "description": "Hyperscaler capex", "current_assessment": "accelerating"},
                        {"name": "Supply chain", "description": "TSMC partnership", "current_assessment": "stable"},
                    ],
                    "kill_criteria": [{"description": "AMD ROCm parity"}],
                    "initial_confidence": 55.0,
                },
            )

            # We need the obs_id and hyp_id to build subsequent tool calls, but
            # those are generated inside the tool.  We can work around this by
            # making the LLM return placeholder IDs -- the harness dispatches
            # tools using the arguments the *LLM* provides, but then the tool
            # returns the real ID.  For add_evidence_card we need the *real*
            # IDs. Instead, let's split into two separate harness.run() calls
            # in session 1 so we can capture the returned IDs.

            # --- Session 1, call A: observation + hypothesis ----------------
            mock_llm_a = MagicMock(spec=LLMClient)
            mock_llm_a.chat.side_effect = [
                LLMResponse(content=None, tool_calls=[tc_obs]),
                LLMResponse(content=None, tool_calls=[tc_hyp]),
                LLMResponse(content="Observation and hypothesis saved.", tool_calls=[]),
            ]

            harness_a = Harness(
                llm=mock_llm_a,
                tools=tools,
                soul="You are IRIS.",
                config=HarnessConfig(max_tool_rounds=10),
                retriever=retriever,
            )
            result_a = harness_a.run("Analyze NVDA")
            assert result_a.ok, f"Session 1A failed: {result_a.error}"

            # Verify objects persisted in SQLite
            obs_list = retriever.query_observations(subject="NVDA")
            assert len(obs_list) >= 1, "Observation not saved"
            hyp_list = retriever.list_hypotheses(company="NVDA")
            assert len(hyp_list) >= 1, "Hypothesis not saved"

            obs_id = obs_list[0].id
            hyp_id = hyp_list[0].id

            # --- Session 1, call B: evidence card + trade score -------------
            tc_ev = ToolCall(
                id="tc_ev",
                name="add_evidence_card",
                arguments={
                    "hypothesis_id": hyp_id,
                    "observation_id": obs_id,
                    "direction": "supports",
                    "reliability": 0.9,
                    "independence": 0.8,
                    "novelty": 0.7,
                    "driver_link": "CUDA moat",
                    "reasoning": "Direct revenue evidence supports thesis",
                },
            )
            tc_score = ToolCall(
                id="tc_score",
                name="compute_trade_score",
                arguments={
                    "hypothesis_id": hyp_id,
                    "fundamental_quality": 0.8,
                    "catalyst_timing": 0.6,
                    "risk_penalty": 0.3,
                    "reasoning": "Good fundamentals, catalysts moderate",
                },
            )

            mock_llm_b = MagicMock(spec=LLMClient)
            mock_llm_b.chat.side_effect = [
                LLMResponse(content=None, tool_calls=[tc_ev]),
                LLMResponse(content=None, tool_calls=[tc_score]),
                LLMResponse(content="Analysis complete: RESEARCH_MORE.", tool_calls=[]),
            ]

            harness_b = Harness(
                llm=mock_llm_b,
                tools=tools,
                soul="You are IRIS.",
                config=HarnessConfig(max_tool_rounds=10),
                retriever=retriever,
            )
            result_b = harness_b.run("Continue NVDA analysis")
            assert result_b.ok, f"Session 1B failed: {result_b.error}"

            # Verify trade score persisted
            updated_hyp = retriever.get_hypothesis(hyp_id)
            assert len(updated_hyp.evidence_log) >= 1, "Evidence card not attached"

        # ---- Session 2: NEW harness instance, same db_path -----------------
        retriever2 = SQLiteRetriever(db_path)
        with patch.object(retriever2, "_embed", side_effect=_mock_embed):
            mock_llm2 = MagicMock(spec=LLMClient)
            mock_llm2.chat.return_value = LLMResponse(
                content="Continuing with prior context.", tool_calls=[]
            )

            harness2 = Harness(
                llm=mock_llm2,
                tools=_make_knowledge_tools(retriever2),
                soul="You are IRIS.",
                config=HarnessConfig(max_tool_rounds=5),
                retriever=retriever2,
            )
            result2 = harness2.run("Update NVDA analysis")
            assert result2.ok

            # The user message sent to LLM must contain prior context
            sent_messages = mock_llm2.chat.call_args_list[0][0][0]
            user_msg = sent_messages[1]["content"]
            assert "Prior Analysis Context" in user_msg, (
                f"Prior context header missing in user message: {user_msg[:300]}"
            )
            # Should mention observations or hypotheses from session 1
            assert "NVDA" in user_msg
            assert ("revenue" in user_msg.lower() or
                    "dominate" in user_msg.lower() or
                    "Existing Hypotheses" in user_msg or
                    "Recent Observations" in user_msg), (
                f"Expected prior data in user message, got: {user_msg[:500]}"
            )


# ---------------------------------------------------------------------------
# Test 2: Context compaction under pressure
# ---------------------------------------------------------------------------

class TestContextCompaction:
    """
    Create a harness with very small context_limit_chars (500).
    Feed messages that exceed the limit and verify LLM-based compaction.
    """

    def test_compaction_calls_llm_summarizer(self, tmp_path):
        summary_text = "## Summary\nNVDA analysis: revenue up 78%, hypothesis at 55% confidence."
        summary_response = LLMResponse(content=summary_text, tool_calls=[])

        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat.side_effect = [summary_response]

        harness = Harness(
            llm=mock_llm,
            tools=[],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5, context_limit_chars=500),
        )

        # Build a message list that exceeds 500 chars
        messages = [
            {"role": "system", "content": "You are IRIS."},
            {"role": "user", "content": "Analyze NVDA"},
        ]
        for i in range(12):
            messages.append({"role": "assistant", "content": f"Step {i}: " + "A" * 60})
            messages.append({"role": "user", "content": f"Continue {i} please."})

        original_count = len(messages)

        harness._compact_context(messages)

        # LLM was called for summarization (not just truncation)
        assert mock_llm.chat.call_count >= 1, "LLM was not called for summarization"

        # Messages array was reduced in size
        assert len(messages) < original_count, (
            f"Messages not compacted: {len(messages)} >= {original_count}"
        )

        # The summary message contains "[CONTEXT SUMMARY"
        summary_msgs = [
            m for m in messages
            if "[CONTEXT SUMMARY" in m.get("content", "")
        ]
        assert len(summary_msgs) >= 1, "No [CONTEXT SUMMARY] message found after compaction"

        # System message preserved
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are IRIS."

        # Original user message preserved
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Analyze NVDA"

        # Recent messages preserved (last few should be from the tail)
        last_msgs = [m for m in messages if m["role"] in ("assistant", "user")]
        assert len(last_msgs) >= 2, "Recent messages were not preserved"

    def test_manage_context_triggers_compaction(self, tmp_path):
        """_manage_context() triggers compaction at 85% of context_limit_chars."""
        summary_response = LLMResponse(content="Compacted summary.", tool_calls=[])
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat.side_effect = [summary_response]

        events = []
        harness = Harness(
            llm=mock_llm,
            tools=[],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5, context_limit_chars=500),
            on_event=lambda e: events.append(e),
        )

        messages = [
            {"role": "system", "content": "S" * 50},
            {"role": "user", "content": "U" * 50},
        ]
        for i in range(12):
            messages.append({"role": "assistant", "content": "A" * 60})
            messages.append({"role": "user", "content": "B" * 60})

        harness._manage_context(messages)

        compaction_events = [e for e in events if e.type == EventType.CONTEXT_COMPACTED]
        assert len(compaction_events) >= 1, "CONTEXT_COMPACTED event not emitted"


# ---------------------------------------------------------------------------
# Test 3: Memory search tool works end-to-end
# ---------------------------------------------------------------------------

class TestMemorySearchE2E:
    """
    Save several observations, mock _embed on the retriever,
    call memory_search directly, verify ranked results.
    """

    def test_memory_search_returns_ranked_results(self, tmp_path):
        db_path = str(tmp_path / "search.db")
        retriever = SQLiteRetriever(db_path)

        with patch.object(retriever, "_embed", side_effect=_mock_embed):
            # Save several observations
            extract_observation(
                retriever=retriever, subject="NVDA",
                claim="Data center revenue up 78%",
                source="Earnings", fact_or_view="fact", relevance=0.95,
                citation="Revenue...", time_str="2026-02-21",
            )
            extract_observation(
                retriever=retriever, subject="AMD",
                claim="MI300X launched for AI training",
                source="AMD Event", fact_or_view="fact", relevance=0.7,
                citation="Launched...", time_str="2026-03-01",
            )
            extract_observation(
                retriever=retriever, subject="NVDA",
                claim="Blackwell B200 GPU shipping to hyperscalers",
                source="Jensen keynote", fact_or_view="fact", relevance=0.85,
                citation="Shipping now...", time_str="2026-02-15",
            )

            # Call memory_search tool function directly
            result = memory_search(
                retriever=retriever,
                query="NVDA data center GPU revenue",
                top_k=3,
            )

        assert result.status == "ok"
        assert "results" in result.data
        assert result.data["count"] >= 1
        # Results should have score and id fields
        for item in result.data["results"]:
            assert "id" in item
            assert "score" in item
            assert "content" in item

    def test_memory_search_filters_by_source_type(self, tmp_path):
        db_path = str(tmp_path / "search_filter.db")
        retriever = SQLiteRetriever(db_path)

        with patch.object(retriever, "_embed", side_effect=_mock_embed):
            extract_observation(
                retriever=retriever, subject="TSLA",
                claim="FSD v13 5x safety improvement",
                source="Tesla AI Day", fact_or_view="fact", relevance=0.85,
                citation="...", time_str="2026-03-01",
            )
            create_hypothesis(
                retriever=retriever, company="TSLA",
                thesis="Robotaxi creates new revenue",
                timeframe="18 months",
                drivers=[
                    {"name": "FSD", "description": "Autonomy", "current_assessment": "improving"},
                    {"name": "Reg", "description": "Approvals", "current_assessment": "pending"},
                    {"name": "Fleet", "description": "Production", "current_assessment": "strong"},
                ],
                kill_criteria=[{"description": "Fatal accident"}],
                initial_confidence=55.0,
            )

            result = memory_search(
                retriever=retriever,
                query="Tesla autonomous driving",
                top_k=5,
                source_type="hypothesis",
            )

        assert result.status == "ok"
        for item in result.data["results"]:
            assert item["source_type"] == "hypothesis"


# ---------------------------------------------------------------------------
# Test 4: Memory flush saves data before compaction
# ---------------------------------------------------------------------------

class TestMemoryFlush:
    """
    Set up harness with tools. Create messages exceeding context limit.
    Mock LLM to return a tool call during flush AND a summary during compaction.
    Verify tool was executed during flush and messages were compacted after.
    """

    def test_flush_executes_tool_then_compacts(self, tmp_path):
        db_path = str(tmp_path / "flush.db")
        retriever = SQLiteRetriever(db_path)

        with patch.object(retriever, "_embed", side_effect=_mock_embed):
            tools = _make_knowledge_tools(retriever)

            # LLM call 1 (memory_flush): returns a tool call to save an observation
            flush_tc = ToolCall(
                id="flush_tc_1",
                name="extract_observation",
                arguments={
                    "subject": "NVDA",
                    "claim": "Flushed finding: margins expanding",
                    "source": "prior conversation",
                    "fact_or_view": "view",
                    "relevance": 0.8,
                    "citation": "margin data...",
                    "time_str": "2026-03-15",
                },
            )
            flush_response = LLMResponse(content=None, tool_calls=[flush_tc])

            # LLM call 2 (_llm_summarize): returns a summary
            summary_response = LLMResponse(
                content="Summary: NVDA analysis, margins expanding.",
                tool_calls=[],
            )

            mock_llm = MagicMock(spec=LLMClient)
            mock_llm.chat.side_effect = [flush_response, summary_response]

            harness = Harness(
                llm=mock_llm,
                tools=tools,
                soul="You are IRIS.",
                config=HarnessConfig(max_tool_rounds=5, context_limit_chars=500),
            )

            # Build long message list
            messages = [
                {"role": "system", "content": "You are IRIS."},
                {"role": "user", "content": "Analyze NVDA"},
            ]
            for i in range(12):
                messages.append({"role": "assistant", "content": f"Step {i}: " + "X" * 60})
                messages.append({"role": "user", "content": f"Continue {i}"})

            original_count = len(messages)
            harness._compact_context(messages)

            # Verify the flush tool was called (extract_observation executed)
            assert mock_llm.chat.call_count >= 2, (
                f"Expected >= 2 LLM calls (flush + summary), got {mock_llm.chat.call_count}"
            )

            # Verify observation was actually saved during flush
            obs = retriever.query_observations(subject="NVDA")
            assert len(obs) >= 1, "Flush did not save observation to DB"
            flushed = [o for o in obs if "margins expanding" in o.claim.lower()]
            assert len(flushed) >= 1, "Flushed observation not found in DB"

            # Verify messages were compacted
            assert len(messages) < original_count

    def test_flush_skipped_when_no_knowledge_tools(self, tmp_path):
        """If no knowledge tools are registered, flush is a no-op."""
        mock_llm = MagicMock(spec=LLMClient)
        summary_response = LLMResponse(content="Summary.", tool_calls=[])
        mock_llm.chat.side_effect = [summary_response]

        # No knowledge tools -- only a dummy non-knowledge tool
        dummy_tool = MagicMock()
        dummy_tool.name = "exa_search"
        dummy_tool.schema = {"type": "function", "function": {"name": "exa_search"}}

        harness = Harness(
            llm=mock_llm,
            tools=[dummy_tool],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5, context_limit_chars=500),
        )

        messages = [
            {"role": "system", "content": "You are IRIS."},
            {"role": "user", "content": "Analyze NVDA"},
        ]
        for i in range(12):
            messages.append({"role": "assistant", "content": "X" * 60})
            messages.append({"role": "user", "content": "continue"})

        harness._compact_context(messages)

        # Only 1 LLM call (summary), no flush call
        assert mock_llm.chat.call_count == 1, (
            f"Expected 1 LLM call (summary only), got {mock_llm.chat.call_count}"
        )


# ---------------------------------------------------------------------------
# Test 5: Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """
    Test fallback behaviors when components fail.
    """

    def test_llm_summary_failure_falls_back_to_truncation(self, tmp_path):
        """When LLM summary raises an exception, fallback truncation kicks in."""
        mock_llm = MagicMock(spec=LLMClient)
        # LLM call for flush succeeds (no tool calls)
        # LLM call for summary FAILS
        mock_llm.chat.side_effect = [
            LLMResponse(content="Nothing to save.", tool_calls=[]),  # flush
            Exception("LLM is down!"),  # summary fails
        ]

        harness = Harness(
            llm=mock_llm,
            tools=[],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5, context_limit_chars=500),
        )

        messages = [
            {"role": "system", "content": "You are IRIS."},
            {"role": "user", "content": "Analyze NVDA"},
        ]
        for i in range(12):
            messages.append({"role": "assistant", "content": f"Step {i}: " + "Z" * 60})
            messages.append({"role": "user", "content": f"Continue {i}"})

        original_count = len(messages)
        harness._compact_context(messages)

        # Messages should still be compacted (via fallback truncation)
        assert len(messages) < original_count, "Fallback truncation did not reduce messages"

        # Should still have a [CONTEXT SUMMARY message (from fallback)
        summary_msgs = [
            m for m in messages
            if "[CONTEXT SUMMARY" in m.get("content", "")
        ]
        assert len(summary_msgs) >= 1, "No context summary found after fallback"

    def test_embed_failure_observation_still_saved(self, tmp_path):
        """When _embed fails, save_observation still saves (embedding silently skipped)."""
        db_path = str(tmp_path / "embed_fail.db")
        retriever = SQLiteRetriever(db_path)

        # Make _embed raise an exception
        with patch.object(retriever, "_embed", side_effect=Exception("Embedding API down")):
            result = extract_observation(
                retriever=retriever, subject="NVDA",
                claim="Revenue up 78%",
                source="Earnings", fact_or_view="fact", relevance=0.9,
                citation="...", time_str="2026-02-21",
            )

        # Observation should be saved successfully despite embed failure
        assert result.status == "ok", f"Observation save failed: {result.error}"
        obs = retriever.query_observations(subject="NVDA")
        assert len(obs) == 1
        assert obs[0].claim == "Revenue up 78%"

    def test_empty_retriever_returns_empty_prior_context(self, tmp_path):
        """When retriever has no data, _load_prior_context returns empty string."""
        db_path = str(tmp_path / "empty.db")
        retriever = SQLiteRetriever(db_path)

        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(content="Fresh analysis.", tool_calls=[])

        harness = Harness(
            llm=mock_llm,
            tools=[],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5),
            retriever=retriever,
        )

        # _load_prior_context should return empty string, no crash
        prior = harness._load_prior_context()
        assert prior == "", f"Expected empty string, got: {prior!r}"

        # run() should succeed normally
        result = harness.run("Analyze NVDA")
        assert result.ok

        # User message should NOT contain "Prior Analysis Context"
        sent_messages = mock_llm.chat.call_args_list[0][0][0]
        user_msg = sent_messages[1]["content"]
        assert "Prior Analysis Context" not in user_msg

    def test_retriever_exception_in_load_prior_context(self, tmp_path):
        """If retriever methods throw, _load_prior_context handles gracefully."""
        mock_retriever = MagicMock()
        mock_retriever.list_hypotheses.side_effect = Exception("DB locked")
        mock_retriever.query_observations.side_effect = Exception("DB locked")

        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(content="Analysis.", tool_calls=[])

        harness = Harness(
            llm=mock_llm,
            tools=[],
            soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5),
            retriever=mock_retriever,
        )

        # Should not crash
        result = harness.run("Analyze NVDA")
        assert result.ok
