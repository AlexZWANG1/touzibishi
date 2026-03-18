import os
import sys
from dotenv import load_dotenv

load_dotenv()

from core.config import EVOLVABLE_PARAMS, DB_PATH, load_soul
from core.harness import Harness, HarnessConfig
from core.invariants import InvariantChecker
from guards.guards import InvestmentGuards
from llm.openai_client import OpenAIClient
from tools.retrieval import SQLiteRetriever
from tools.base import Tool
from tools.search import perplexity_search, PERPLEXITY_SEARCH_SCHEMA
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


def build_harness(db_path: str = None) -> tuple[Harness, SQLiteRetriever]:
    db = db_path or DB_PATH
    retriever = SQLiteRetriever(db)
    soul = load_soul()

    external_tools = [
        Tool(perplexity_search, PERPLEXITY_SEARCH_SCHEMA),
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
        guards=InvestmentGuards(),
        invariants=InvariantChecker(),
        retriever=retriever,
        soul=soul,
        config=HarnessConfig(
            max_tool_rounds=EVOLVABLE_PARAMS["max_tool_rounds"],
            compress_threshold_chars=EVOLVABLE_PARAMS["compress_threshold_chars"],
        ),
    )
    return harness, retriever


def run_cli(query: str, docs: list[str] = None):
    harness, _ = build_harness()
    print(f"\nAnalyzing: {query}\n{'='*60}")
    result = harness.run(query, context_docs=docs)
    if result.ok:
        print(f"\nAnalysis Complete\n{result.reply}")
    else:
        print(f"\nAnalysis Failed: {result.error}")
    print(f"\nTool calls: {len(result.tool_log)}")
    print(f"Tokens: {result.total_input_tokens} in / {result.total_output_tokens} out")
    return result


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "分析 NVDA 在 AI 基础设施赛道的投资机会"
    run_cli(query)
