import sys
from dotenv import load_dotenv

load_dotenv()

from core.config import load_config, load_soul, register_skill_config, DB_PATH, get as config_get
from core.harness import Harness, HarnessConfig, HarnessEvent, EventType
from core.loop_detector import LoopDetectionConfig
from core.skill_loader import load_skills
from llm.openai_client import OpenAIClient
from tools.retrieval import SQLiteRetriever
from tools.base import Tool
from tools.search import (
    exa_search, EXA_SEARCH_SCHEMA,
    web_fetch, WEB_FETCH_SCHEMA,
)
from tools.financials import (
    financials, FINANCIALS_SCHEMA,
    macro, MACRO_SCHEMA,
)
from tools.market import (
    quote, QUOTE_SCHEMA,
    history, HISTORY_SCHEMA,
)
from tools.unified_memory import (
    remember, REMEMBER_SCHEMA,
    recall, RECALL_SCHEMA,
    search_knowledge, SEARCH_KNOWLEDGE_SCHEMA,
)
from tools.sec_filing import sec_filing, SEC_FILING_SCHEMA
from tools.transcripts import transcript, TRANSCRIPT_SCHEMA
from tools.news_feed import news_feed, NEWS_FEED_SCHEMA


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
        symbol = "OK" if status == "ok" else "ERR"
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
    mode: str = "analysis",
) -> tuple[Harness, SQLiteRetriever]:
    cfg = load_config()
    h = cfg["harness"]
    budget_cfg = cfg.get("budget", {})
    loop_cfg = cfg.get("loop_detection", {})
    skills_cfg = cfg.get("skills", {})
    mode_cfg = cfg.get("modes", {}).get(mode, {})

    # Mode overrides harness defaults
    max_tool_rounds = mode_cfg.get("max_tool_rounds", h.get("max_tool_rounds", 25))
    max_total_tool_calls = mode_cfg.get("max_total_tool_calls", h.get("max_total_tool_calls", 60))
    max_wall_time = mode_cfg.get("max_wall_time_seconds", h.get("max_wall_time_seconds", 480.0))
    tool_injection_mode = mode_cfg.get("tool_injection_mode", h.get("tool_injection_mode", "dynamic"))
    mode_exposed_tools = mode_cfg.get("always_exposed_tools")
    always_exposed = tuple(mode_exposed_tools) if mode_exposed_tools else tuple(
        h.get("always_exposed_tools", ["remember", "recall"])
    )

    db = db_path or DB_PATH
    retriever = SQLiteRetriever(db)

    # Core tools — external data sources
    # panel_type declares which frontend panel extractor to use (see sessions.py)
    core_tools = [
        Tool(exa_search, EXA_SEARCH_SCHEMA),
        Tool(web_fetch, WEB_FETCH_SCHEMA),
        Tool(financials, FINANCIALS_SCHEMA, panel_type="data"),
        Tool(macro, MACRO_SCHEMA),
        Tool(quote, QUOTE_SCHEMA, panel_type="quote"),
        Tool(history, HISTORY_SCHEMA),
        Tool(sec_filing, SEC_FILING_SCHEMA),
        Tool(transcript, TRANSCRIPT_SCHEMA),
        Tool(news_feed, NEWS_FEED_SCHEMA),
    ]

    # Memory tools — is_knowledge=True means they must be flushed before compaction
    memory_tools = [
        Tool(remember, REMEMBER_SCHEMA, retriever=retriever, is_knowledge=True),
        Tool(recall, RECALL_SCHEMA, retriever=retriever, panel_type="memory_recall"),
        Tool(search_knowledge, SEARCH_KNOWLEDGE_SCHEMA, retriever=retriever),
    ]

    # Skill tools — mode-filtered
    skills_dir = skills_cfg.get("dir", "./skills")
    skill_name_list = mode_cfg.get("skills")  # None = load all
    skill_tools, skill_soul = load_skills(
        skills_dir,
        context={"retriever": retriever, "mode": mode},
        skill_names=skill_name_list,
    )

    # Register mode in skill config so tools can read it
    register_skill_config("_runtime", {"mode": mode})

    # Soul — mode-filtered
    soul_file_list = mode_cfg.get("soul_files")  # None = load all
    base_soul = load_soul(file_list=soul_file_list)
    full_soul = base_soul
    if skill_soul:
        full_soul = base_soul + "\n\n---\n\n" + skill_soul

    # Tool set — filter by mode's always_exposed_tools if defined
    all_candidate_tools = core_tools + memory_tools + skill_tools
    if mode_exposed_tools:
        exposed_set = set(mode_exposed_tools)
        all_tools = [t for t in all_candidate_tools if t.name in exposed_set]
    else:
        all_tools = all_candidate_tools

    harness = Harness(
        llm=OpenAIClient(),
        tools=all_tools,
        soul=full_soul,
        config=HarnessConfig(
            max_tool_rounds=max_tool_rounds,
            max_total_tool_calls=max_total_tool_calls,
            max_wall_time_seconds=max_wall_time,
            max_retries=h.get("max_retries", 3),
            retry_base_delay=h.get("retry_base_delay", 1.0),
            context_limit_chars=h.get("context_limit_chars", 300000),
            compress_threshold_chars=h.get("compress_threshold_chars", 5000),
            tool_compress_overrides=h.get("tool_compress_overrides", {}),
            tool_injection_mode=tool_injection_mode,
            max_tools_per_round=h.get("max_tools_per_round", 10),
            always_exposed_tools=always_exposed,
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
            # Deep research config
            deep_research=config_get("deep_research.enabled", False),
            max_eval_rounds=config_get("deep_research.max_eval_rounds", 5),
            min_tools_for_eval=config_get("deep_research.min_tools_for_eval", 2),
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
