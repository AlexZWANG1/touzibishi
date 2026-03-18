import sys
from dotenv import load_dotenv

load_dotenv()

from core.config import load_config, load_soul, DB_PATH
from core.harness import Harness, HarnessConfig, HarnessEvent, EventType
from core.loop_detector import LoopDetectionConfig
from llm.openai_client import OpenAIClient
from tools.retrieval import SQLiteRetriever
from tools.base import Tool
from tools.search import (
    exa_search, EXA_SEARCH_SCHEMA,
    web_fetch, WEB_FETCH_SCHEMA,
)
from tools.financials import (
    fmp_get_financials, FMP_GET_FINANCIALS_SCHEMA,
    fred_get_macro, FRED_GET_MACRO_SCHEMA,
)
from tools.knowledge import (
    extract_observation, EXTRACT_OBSERVATION_SCHEMA,
    create_hypothesis, CREATE_HYPOTHESIS_SCHEMA,
    add_evidence_card, ADD_EVIDENCE_CARD_SCHEMA,
    run_valuation, RUN_VALUATION_SCHEMA,
    compute_trade_score, COMPUTE_TRADE_SCORE_SCHEMA,
    write_audit_trail, WRITE_AUDIT_TRAIL_SCHEMA,
    query_knowledge, QUERY_KNOWLEDGE_SCHEMA,
    memory_search, MEMORY_SEARCH_SCHEMA,
)


def _cli_event_handler(event: HarnessEvent):
    """Print harness events to console for CLI mode."""
    if event.type == EventType.RUN_START:
        print(f"[Run] {event.data.get('run_id', '-')}")
    elif event.type == EventType.TURN_START:
        tools = event.data.get("tools_exposed", [])
        budget = event.data.get("budget", {})
        rounds = budget.get("tool_rounds", {})
        loop = event.data.get("loop_status", {})
        print(
            f"  [Round {event.data.get('round', '?')}] "
            f"tools_exposed={len(tools)} "
            f"rounds={rounds.get('used', '?')}/{rounds.get('limit', '?')} "
            f"loop={loop}"
        )
    elif event.type == EventType.TOOL_START:
        print(f"    → {event.data.get('tool', '?')}()")
    elif event.type == EventType.TOOL_END:
        status = event.data.get('status', '?')
        symbol = "✓" if status == "ok" else "✗"
        print(f"    {symbol} {event.data.get('tool', '?')} [{status}]")
    elif event.type == EventType.LOOP_DETECTED:
        print(f"  [loop] {event.data.get('message', '')}")
    elif event.type == EventType.BUDGET_TRIMMED:
        print(
            f"  [budget trim] planned={event.data.get('planned', '?')} "
            f"allowed={event.data.get('allowed', '?')}"
        )
    elif event.type == EventType.CONTEXT_COMPACTED:
        print(f"  [context compacted]")
    elif event.type == EventType.RETRY:
        if event.data.get("failed"):
            print(f"  [retry failed: {event.data.get('error', '?')}]")
        else:
            print(f"  [retry #{event.data.get('attempt')} in {event.data.get('delay', 0):.1f}s]")
    elif event.type == EventType.TEXT_DELTA:
        print(event.data.get("content", ""), end="", flush=True)
    elif event.type == EventType.ABORTED:
        print("\n  [ABORTED]")


def build_harness(
    db_path: str = None,
    on_event=None,
    streaming: bool = False,
) -> tuple[Harness, SQLiteRetriever]:
    cfg = load_config()
    h = cfg["harness"]
    budget_cfg = cfg.get("budget", {})
    loop_cfg = cfg.get("loop_detection", {})

    db = db_path or DB_PATH
    retriever = SQLiteRetriever(db)
    soul = load_soul()

    external_tools = [
        Tool(exa_search, EXA_SEARCH_SCHEMA),
        Tool(web_fetch, WEB_FETCH_SCHEMA),
        Tool(fmp_get_financials, FMP_GET_FINANCIALS_SCHEMA),
        Tool(fred_get_macro, FRED_GET_MACRO_SCHEMA),
    ]

    knowledge_tools = [
        Tool(extract_observation, EXTRACT_OBSERVATION_SCHEMA, retriever=retriever),
        Tool(create_hypothesis, CREATE_HYPOTHESIS_SCHEMA, retriever=retriever),
        Tool(add_evidence_card, ADD_EVIDENCE_CARD_SCHEMA, retriever=retriever),
        Tool(run_valuation, RUN_VALUATION_SCHEMA, retriever=retriever),
        Tool(compute_trade_score, COMPUTE_TRADE_SCORE_SCHEMA, retriever=retriever),
        Tool(write_audit_trail, WRITE_AUDIT_TRAIL_SCHEMA, retriever=retriever),
        Tool(query_knowledge, QUERY_KNOWLEDGE_SCHEMA, retriever=retriever),
        Tool(memory_search, MEMORY_SEARCH_SCHEMA, retriever=retriever),
    ]

    harness = Harness(
        llm=OpenAIClient(),
        tools=external_tools + knowledge_tools,
        soul=soul,
        config=HarnessConfig(
            max_tool_rounds=h.get("max_tool_rounds", 25),
            max_total_tool_calls=h.get("max_total_tool_calls", 60),
            max_wall_time_seconds=h.get("max_wall_time_seconds", 480.0),
            max_retries=h.get("max_retries", 3),
            retry_base_delay=h.get("retry_base_delay", 1.0),
            context_limit_chars=h.get("context_limit_chars", 300000),
            compress_threshold_chars=h.get("compress_threshold_chars", 5000),
            tool_compress_overrides=h.get("tool_compress_overrides", {}),
            tool_injection_mode=h.get("tool_injection_mode", "dynamic"),
            max_tools_per_round=h.get("max_tools_per_round", 10),
            always_exposed_tools=tuple(h.get("always_exposed_tools", ["query_knowledge", "memory_search"])),
            tool_triggers=h.get("tool_triggers", {}),
            include_flush_in_tool_rounds=budget_cfg.get("include_flush_in_tool_rounds", True),
            include_compaction_in_tool_rounds=budget_cfg.get("include_compaction_in_tool_rounds", True),
            pre_round_trim=budget_cfg.get("pre_round_trim", True),
            loop_detection=LoopDetectionConfig(
                generic_repeat_threshold=loop_cfg.get("generic_repeat_threshold", 3),
                ping_pong_threshold=loop_cfg.get("ping_pong_threshold", 3),
                no_progress_threshold=loop_cfg.get("no_progress_threshold", 3),
                action=loop_cfg.get("action", "steer_then_stop"),
            ),
            streaming=streaming,
        ),
        on_event=on_event,
        retriever=retriever,
    )
    return harness, retriever


def run_cli(query: str, docs: list[str] = None):
    harness, _ = build_harness(on_event=_cli_event_handler, streaming=True)
    print(f"\nAnalyzing: {query}\n{'='*60}")
    result = harness.run(query, context_docs=docs)
    if result.ok:
        if not harness.config.streaming:
            print(f"\n{result.reply}")
        print()
    else:
        print(f"\nAnalysis Failed: {result.error}")
    print(f"Run ID: {result.run_id}")
    print(f"Tool calls: {len(result.tool_log)}")
    print(f"Tokens: {result.total_input_tokens} in / {result.total_output_tokens} out")
    if result.budget_breakdown:
        rounds = result.budget_breakdown.get("tool_rounds", {})
        tools = result.budget_breakdown.get("tool_calls", {})
        print(
            f"Budget: rounds={rounds.get('counted_total', 0)}/{rounds.get('limit', 0)}, "
            f"tool_calls={tools.get('total', 0)}/{tools.get('limit', 0)}"
        )
    return result


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "分析 NVDA 在 AI 基础设施赛道的投资机会"
    run_cli(query)
