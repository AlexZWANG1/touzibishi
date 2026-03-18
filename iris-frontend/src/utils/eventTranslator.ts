import type { Phase, EventColor } from "@/types/analysis";

const TOOL_MESSAGE_MAP: Record<string, (args: Record<string, unknown>) => string> = {
  exa_search: (args) => `搜索: "${args.query || ""}"`,
  web_fetch: (args) => {
    try {
      const url = new URL(args.url as string);
      return `阅读: ${url.hostname}`;
    } catch {
      return `阅读: ${args.url || "网页"}`;
    }
  },
  fmp_get_financials: (args) =>
    `拉取 ${args.ticker || ""} ${args.statement_type || "财务"} 数据`,
  fred_get_macro: (args) => `拉取宏观数据: ${args.series_id || ""}`,
  recall_memory: (args) => `回忆 ${args.company || ""} 历史分析`,
  save_memory: () => `保存分析记忆`,
  build_dcf: () => `构建 DCF 模型`,
  get_comps: (args) => `对比同行: ${args.peers || ""}`,
  extract_observation: (args) => {
    const claim = String(args.claim || "");
    return `提取观察: ${claim.slice(0, 40)}${claim.length > 40 ? "..." : ""}`;
  },
  create_hypothesis: (args) => `创建投资假说: ${args.company || ""}`,
  add_evidence_card: () => `评估证据`,
  memory_search: (args) => {
    const query = String(args.query || "");
    return `搜索相关记忆: ${query.slice(0, 30)}${query.length > 30 ? "..." : ""}`;
  },
};

export const TOOL_PHASE_MAP: Record<string, Phase> = {
  recall_memory: "gather",
  exa_search: "gather",
  web_fetch: "gather",
  fmp_get_financials: "gather",
  fred_get_macro: "gather",
  memory_search: "gather",
  extract_observation: "analyze",
  create_hypothesis: "analyze",
  add_evidence_card: "analyze",
  build_dcf: "evaluate",
  get_comps: "evaluate",
  save_memory: "finalize",
};

const PHASE_COLOR_MAP: Record<Phase, EventColor> = {
  gather: "green",
  analyze: "blue",
  evaluate: "amber",
  finalize: "gray",
};

export const TOOL_TAB_MAP: Record<string, string> = {
  fmp_get_financials: "data",
  fred_get_macro: "data",
  build_dcf: "model",
  get_comps: "comps",
  recall_memory: "memory",
};

export function translateToolStart(
  tool: string,
  args: Record<string, unknown>
): { message: string; phase: Phase; color: EventColor } {
  const messageFn = TOOL_MESSAGE_MAP[tool];
  const message = messageFn ? messageFn(args) : `执行: ${tool}`;
  const phase = TOOL_PHASE_MAP[tool] || "gather";
  const color = PHASE_COLOR_MAP[phase];
  return { message, phase, color };
}

export function inferPhase(tool: string): Phase {
  return TOOL_PHASE_MAP[tool] || "gather";
}
