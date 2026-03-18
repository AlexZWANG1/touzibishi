import sys
from dotenv import load_dotenv

load_dotenv()

from core.config import load_config, load_soul, DB_PATH
from core.harness import Harness, HarnessConfig, HarnessEvent, EventType
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
)


def _cli_event_handler(event: HarnessEvent):
    """Print harness events to console for CLI mode."""
    if event.type == EventType.TURN_START:
        print(f"  [Round {event.data.get('round', '?')}] phase={event.data.get('phase', '?')}")
    elif event.type == EventType.TOOL_START:
        print(f"    → {event.data.get('tool', '?')}()")
    elif event.type == EventType.TOOL_END:
        status = event.data.get('status', '?')
        symbol = "✓" if status == "ok" else "✗"
        print(f"    {symbol} {event.data.get('tool', '?')} [{status}]")
    elif event.type == EventType.PHASE_CHANGE:
        print(f"  ── Phase: {event.data.get('from')} → {event.data.get('to')} ──")
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
    ]

    harness = Harness(
        llm=OpenAIClient(),
        tools=external_tools + knowledge_tools,
        soul=soul,
        config=HarnessConfig(
            max_tool_rounds=h["max_tool_rounds"],
            max_retries=h["max_retries"],
            retry_base_delay=h["retry_base_delay"],
            context_limit_chars=h["context_limit_chars"],
            compress_threshold_chars=h["compress_threshold_chars"],
            streaming=streaming,
        ),
        on_event=on_event,
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
    print(f"Tool calls: {len(result.tool_log)}")
    print(f"Tokens: {result.total_input_tokens} in / {result.total_output_tokens} out")
    return result


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "分析 NVDA 在 AI 基础设施赛道的投资机会"
    run_cli(query)
