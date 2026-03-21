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
  financials: (args) =>
    `拉取 ${args.ticker || ""} ${args.statement_type || "财务"} 数据`,
  macro: (args) => `拉取宏观数据: ${args.series_id || ""}`,
  quote: (args) => `获取行情: ${args.ticker || ""}`,
  history: (args) => `读取历史价格: ${args.ticker || ""}`,
  valuation: (args) => `估值计算: ${args.mode || "full"}`,
  create_hypothesis: (args) => `创建投资假说: ${args.company || ""}`,
  add_evidence_card: () => `评估证据`,
  remember: () => `写入记忆`,
  recall: (args) => `检索记忆: ${args.subject || ""}`,
  search_knowledge: (args) => `检索知识库: ${args.query || ""}`,
  generate_trade_signal: (args) => `生成交易信号: ${args.ticker || ""}`,
  get_portfolio: () => `查看持仓`,
};

export const TOOL_PHASE_MAP: Record<string, Phase> = {
  exa_search: "gather",
  web_fetch: "gather",
  financials: "gather",
  macro: "gather",
  quote: "gather",
  history: "gather",
  create_hypothesis: "analyze",
  add_evidence_card: "analyze",
  valuation: "evaluate",
  remember: "finalize",
  recall: "gather",
  search_knowledge: "gather",
  generate_trade_signal: "evaluate",
  get_portfolio: "finalize",
};

const PHASE_COLOR_MAP: Record<Phase, EventColor> = {
  gather: "green",
  analyze: "blue",
  evaluate: "amber",
  finalize: "gray",
};

export const TOOL_TAB_MAP: Record<string, string> = {
  financials: "data",
  macro: "data",
  quote: "data",
  history: "data",
  valuation: "model",
  generate_trade_signal: "strategy",
  get_portfolio: "strategy",
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
