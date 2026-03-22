/**
 * Unified tool registry — single source of truth for tool metadata.
 * Replaces the 3 separate lists in eventTranslator, StreamingTimeline, and TimelineItem.
 */
import type { Phase, EventColor } from "@/types/analysis";

interface ToolDef {
  /** Chinese label shown in timeline */
  label: string;
  /** Which analysis phase this tool belongs to */
  phase: Phase;
  /** Which panel tab this tool populates (if any) */
  tab?: string;
}

const PHASE_COLORS: Record<Phase, EventColor> = {
  gather: "green",
  analyze: "blue",
  evaluate: "amber",
  finalize: "gray",
};

/** Ordered phase index for monotonic phase progression */
export const PHASE_ORDER: Record<Phase, number> = {
  gather: 0,
  analyze: 1,
  evaluate: 2,
  finalize: 3,
};

const REGISTRY: Record<string, ToolDef> = {
  // --- Gather phase ---
  recall: { label: "检索记忆", phase: "gather" },
  recall_memory: { label: "回忆历史", phase: "gather" },
  memory_search: { label: "搜索记忆", phase: "gather" },
  search_knowledge: { label: "检索知识库", phase: "gather" },
  query_knowledge: { label: "查询知识", phase: "gather" },
  financials: { label: "拉取财报", phase: "gather", tab: "data" },
  fmp_get_financials: { label: "拉取财报", phase: "gather", tab: "data" },
  macro: { label: "宏观数据", phase: "gather", tab: "data" },
  fred_get_macro: { label: "宏观数据", phase: "gather", tab: "data" },
  quote: { label: "获取报价", phase: "gather", tab: "data" },
  yf_quote: { label: "获取报价", phase: "gather", tab: "data" },
  history: { label: "历史行情", phase: "gather", tab: "data" },
  yf_history: { label: "历史行情", phase: "gather", tab: "data" },
  exa_search: { label: "搜索资讯", phase: "gather" },
  web_fetch: { label: "抓取网页", phase: "gather" },
  transcript: { label: "财报电话会", phase: "gather" },

  // --- Analyze phase ---
  create_hypothesis: { label: "形成假说", phase: "analyze" },
  add_evidence_card: { label: "添加证据", phase: "analyze" },
  extract_observation: { label: "提取观察", phase: "analyze" },
  emit_report: { label: "输出研究报告", phase: "finalize" },

  // --- Evaluate phase ---
  valuation: { label: "统一估值", phase: "evaluate", tab: "model" },
  build_dcf: { label: "构建 DCF", phase: "evaluate", tab: "model" },
  get_comps: { label: "可比分析", phase: "evaluate", tab: "comps" },
  generate_trade_signal: { label: "交易信号", phase: "evaluate", tab: "strategy" },
  check_calibration: { label: "校准检查", phase: "evaluate" },

  // --- Finalize phase ---
  remember: { label: "写入记忆", phase: "finalize" },
  save_memory: { label: "保存记忆", phase: "finalize" },
  get_portfolio: { label: "查看组合", phase: "finalize", tab: "strategy" },
};

/** Get the display label for a tool, fallback to tool name */
export function getToolLabel(tool: string): string {
  return REGISTRY[tool]?.label || tool;
}

/** Get the phase for a tool, fallback to "gather" */
export function getToolPhase(tool: string): Phase {
  return REGISTRY[tool]?.phase || "gather";
}

/** Get the phase color */
export function getPhaseColor(phase: Phase): EventColor {
  return PHASE_COLORS[phase];
}

/** Get the tab a tool populates (if any) */
export function getToolTab(tool: string): string | undefined {
  return REGISTRY[tool]?.tab;
}

/** Build a human-readable message for a tool_start event */
export function buildToolMessage(tool: string, args: Record<string, unknown>): string {
  switch (tool) {
    case "exa_search":
      return `搜索: "${args.query || ""}"`;
    case "web_fetch":
      try {
        return `阅读: ${new URL(args.url as string).hostname}`;
      } catch {
        return `阅读: ${args.url || "网页"}`;
      }
    case "financials":
    case "fmp_get_financials":
      return `拉取 ${args.ticker || ""} ${args.statement_type || "财务"} 数据`;
    case "macro":
    case "fred_get_macro":
      return `拉取宏观数据: ${args.series_id || ""}`;
    case "quote":
    case "yf_quote":
      return `获取行情: ${args.ticker || ""}`;
    case "history":
    case "yf_history":
      return `读取历史价格: ${args.ticker || ""}`;
    case "valuation":
      return `估值计算: ${args.mode || "full"}`;
    case "create_hypothesis":
      return `创建投资假说: ${args.company || ""}`;
    case "recall":
    case "recall_memory":
      return `检索记忆: ${args.subject || ""}`;
    case "search_knowledge":
    case "query_knowledge":
      return `检索知识库: ${args.query || ""}`;
    case "generate_trade_signal":
      return `生成交易信号: ${args.ticker || ""}`;
    default:
      return REGISTRY[tool]?.label || `执行: ${tool}`;
  }
}

/** Check if a tool name is known */
export function isKnownTool(tool: string): boolean {
  return tool in REGISTRY;
}

/** Get all known tool names (for thinking text hint extraction) */
export function getKnownToolNames(): string[] {
  return Object.keys(REGISTRY);
}
