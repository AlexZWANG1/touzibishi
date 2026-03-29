import { create } from "zustand";
import type {
  PageState,
  Phase,
  ActiveTab,
  TimelineEvent,
  PendingQuestion,
  DataPanelState,
  ModelPanelState,
  CompsPanelState,
  StrategyPanelState,
  MemoryPanelState,
  FundamentalsPanelState,
  AnalysisSnapshot,
} from "@/types/analysis";
import type { SSEEvent } from "@/types/api";
import { buildToolMessage, getToolPhase, getPhaseColor, PHASE_ORDER } from "@/utils/toolRegistry";
import * as api from "@/utils/api";

interface AnalysisStore {
  pageState: PageState;
  isReplay: boolean;
  analysisId: string | null;
  analysisQuery: string;
  timeline: TimelineEvent[];
  reasoningText: string;
  thinkingText: string;
  _rawTextBuffer: string;
  currentPhase: Phase;
  pendingQuestion: PendingQuestion | null;
  activeTab: ActiveTab;
  lastUserTabSwitch: number;
  dataPanel: DataPanelState;
  modelPanel: ModelPanelState;
  compsPanel: CompsPanelState;
  strategyPanel: StrategyPanelState;
  memoryPanel: MemoryPanelState;
  fundamentalsPanel: FundamentalsPanelState;

  resumable: boolean;

  startAnalysis: (query: string, contextDocs?: string[]) => Promise<void>;
  sendSteering: (message: string) => Promise<void>;
  continueAnalysis: (message: string) => Promise<void>;
  resumeAnalysis: (message: string) => Promise<void>;
  respondToInput: (response: string) => Promise<void>;
  setActiveTab: (tab: ActiveTab) => void;
  handleSSEEvent: (event: SSEEvent) => void;
  loadSnapshot: (snapshot: AnalysisSnapshot) => void;
  reset: () => void;
}

const initialDataPanel: DataPanelState = {
  metrics: [],
  financialTables: [],
  loading: false,
};

const initialModelPanel: ModelPanelState = {
  fairValue: null,
  assumptions: [],
  impliedMultiples: [],
  sensitivityData: [],
  sensitivityRowLabel: "WACC",
  sensitivityColLabel: "Terminal Growth",
  sensitivityRowValues: [],
  sensitivityColValues: [],
  yearByYear: [],
  loading: false,
};

const initialCompsPanel: CompsPanelState = {
  peers: [],
  scatterData: [],
  scatterXLabel: "EV/EBITDA",
  scatterYLabel: "Revenue Growth",
  loading: false,
};

const initialStrategyPanel: StrategyPanelState = {
  signal: null,
  portfolio: null,
  loading: false,
};

const initialMemoryPanel: MemoryPanelState = {
  calibrationHits: 0,
  calibrationMisses: 0,
  recentRecalls: [],
  loading: false,
};

const initialFundamentalsPanel: FundamentalsPanelState = {
  title: "",
  content: "",
  loading: false,
};

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  pageState: "IDLE",
  isReplay: false,
  analysisId: null,
  analysisQuery: "",
  timeline: [],
  reasoningText: "",
  thinkingText: "",
  _rawTextBuffer: "",
  currentPhase: "gather",
  pendingQuestion: null,
  activeTab: "report",
  lastUserTabSwitch: 0,
  resumable: false,
  dataPanel: initialDataPanel,
  modelPanel: initialModelPanel,
  compsPanel: initialCompsPanel,
  strategyPanel: initialStrategyPanel,
  memoryPanel: initialMemoryPanel,
  fundamentalsPanel: initialFundamentalsPanel,

  startAnalysis: async (query: string, contextDocs?: string[]) => {
    set({ pageState: "RUNNING", analysisQuery: query, timeline: [], reasoningText: "", thinkingText: "", _rawTextBuffer: "", currentPhase: "gather", isReplay: false });
    try {
      const response = await api.startAnalysis({
        query,
        contextDocs,
      });
      set({ analysisId: response.analysisId });
    } catch (error) {
      set({ pageState: "IDLE" });
      console.error("Failed to start analysis:", error);
    }
  },

  sendSteering: async (message: string) => {
    const { analysisId } = get();
    if (!analysisId) return;
    try {
      await api.sendSteering(analysisId, { message });
      set((state) => ({
        timeline: [
          ...state.timeline,
          {
            id: `user-${Date.now()}`,
            timestamp: Date.now(),
            tool: "user_steering",
            message: message,
            phase: state.currentPhase,
            color: "purple",
            status: "complete",
          },
        ],
      }));
    } catch (error) {
      console.error("Failed to send steering:", error);
    }
  },

  continueAnalysis: async (message: string) => {
    const { analysisId } = get();
    if (!analysisId) return;
    try {
      await api.continueAnalysis(analysisId, message);
      // Add user message to timeline + insert turn marker in text buffer
      set((state) => {
        const newRaw = state._rawTextBuffer + `\n\n<!---TURN--->\n${message}\n<!---TURN--->\n\n`;
        const { reasoning, thinking } = _splitThinkingBlocks(newRaw);
        return {
        pageState: "RUNNING",
        currentPhase: "gather",
        _rawTextBuffer: newRaw,
        reasoningText: reasoning,
        thinkingText: thinking,
        timeline: [
          ...state.timeline,
          {
            id: `user-continue-${Date.now()}`,
            timestamp: Date.now(),
            tool: "user_continue",
            message: message,
            phase: "gather" as const,
            color: "purple" as const,
            status: "complete" as const,
          },
        ],
      };});
    } catch (error) {
      console.error("Failed to continue analysis:", error);
    }
  },

  resumeAnalysis: async (message: string) => {
    const { analysisId } = get();
    if (!analysisId) return;
    try {
      const response = await api.resumeAnalysis(analysisId, message);
      set((state) => {
        const newRaw = state._rawTextBuffer + `\n\n<!---TURN--->\n${message}\n<!---TURN--->\n\n`;
        const { reasoning, thinking } = _splitThinkingBlocks(newRaw);
        return {
          pageState: "RUNNING",
          isReplay: false,
          resumable: true,
          currentPhase: "gather",
          analysisId: response.analysisId,
          _rawTextBuffer: newRaw,
          reasoningText: reasoning,
          thinkingText: thinking,
          timeline: [
            ...state.timeline,
            {
              id: `user-resume-${Date.now()}`,
              timestamp: Date.now(),
              tool: "user_continue",
              message: message,
              phase: "gather" as const,
              color: "purple" as const,
              status: "complete" as const,
            },
          ],
        };
      });
    } catch (error) {
      console.error("Failed to resume analysis:", error);
    }
  },

  respondToInput: async (response: string) => {
    const { analysisId } = get();
    if (!analysisId) return;
    try {
      await api.respondToInput(analysisId, { response });
      set((state) => ({
        pageState: "RUNNING",
        pendingQuestion: null,
        timeline: [
          ...state.timeline,
          {
            id: `response-${Date.now()}`,
            timestamp: Date.now(),
            tool: "user_response",
            message: response,
            phase: state.currentPhase,
            color: "purple",
            status: "complete",
          },
        ],
      }));
    } catch (error) {
      console.error("Failed to respond to input:", error);
    }
  },

  setActiveTab: (tab: ActiveTab) => {
    set({ activeTab: tab, lastUserTabSwitch: Date.now() });
  },

  handleSSEEvent: (event: SSEEvent) => {
    const state = get();

    switch (event.type) {
      case "tool_start": {
        const { tool, args } = event.data as {
          tool: string;
          args: Record<string, unknown>;
        };
        const message = buildToolMessage(tool, args || {});
        const phase = getToolPhase(tool);
        const color = getPhaseColor(phase);
        // Backend doesn't send call_id, so we generate one client-side
        const id = `tool-${tool}-${event.timestamp}`;
        set((s) => ({
          currentPhase: PHASE_ORDER[phase] >= PHASE_ORDER[s.currentPhase] ? phase : s.currentPhase,
          timeline: [
            ...s.timeline,
            {
              id,
              timestamp: event.timestamp,
              tool,
              message,
              phase,
              color,
              status: "running",
            },
          ],
        }));
        break;
      }

      case "tool_end": {
        const { tool, status, result } = event.data as {
          tool: string;
          status: string;
          result?: unknown;
        };
        set((s) => {
          // Find the last running timeline entry with this tool name
          const idx = [...s.timeline].reverse().findIndex(
            (item) => item.tool === tool && item.status === "running"
          );
          if (idx === -1) return {};

          const actualIdx = s.timeline.length - 1 - idx;
          const updatedTimeline = [...s.timeline];
          updatedTimeline[actualIdx] = {
            ...updatedTimeline[actualIdx],
            status: status === "error" ? "error" : "complete",
          };
          return { timeline: updatedTimeline };
        });

        // Keep right-side chat stable; skill tabs are user-driven.
        // We no longer auto-switch tabs on tool completion.

        // Extract panel data from tool results
        if (result && typeof result === "object") {
          _extractPanelData(tool, result as Record<string, unknown>, set);
        }
        break;
      }

      case "text_delta": {
        const content = event.data.content as string;
        if (content) {
          set((s) => {
            // Append to raw buffer, then reparse from complete text.
            // This handles <thinking> tags split across SSE chunks correctly.
            const raw = s._rawTextBuffer + content;
            const { reasoning, thinking } = _splitThinkingBlocks(raw);
            return {
              _rawTextBuffer: raw,
              reasoningText: reasoning,
              thinkingText: thinking,
            };
          });
        }
        break;
      }

      case "text": {
        const content = event.data.content as string;
        if (content) {
          const { reasoning, thinking } = _splitThinkingBlocks(content);
          set({
            _rawTextBuffer: content,
            reasoningText: reasoning,
            thinkingText: thinking,
          });
        }
        break;
      }

      case "user_input_needed": {
        const { question, context, options } = event.data as {
          question: string;
          context: string;
          options: string[];
        };
        set({ pageState: "WAITING", pendingQuestion: { question, context, options } });
        break;
      }

      case "analysis_complete": {
        const { ok, reply, error } = event.data as {
          ok: boolean;
          reply?: string;
          error?: string;
        };
        set((s) => {
          // If streaming produced text, use it. Otherwise parse the reply fallback
          // through _splitThinkingBlocks so thinking tags never leak into reasoningText.
          let finalReasoning = s.reasoningText;
          let finalThinking = s.thinkingText;
          let finalRaw = s._rawTextBuffer;
          if (!finalReasoning && ok && reply) {
            const parsed = _splitThinkingBlocks(reply);
            finalReasoning = parsed.reasoning;
            finalThinking = parsed.thinking || finalThinking;
            finalRaw = reply;
          }
          return {
          pageState: "COMPLETE",
          reasoningText: finalReasoning,
          thinkingText: finalThinking,
          _rawTextBuffer: finalRaw,
          timeline: [
            ...s.timeline,
            {
              id: `complete-${event.timestamp}`,
              timestamp: event.timestamp,
              tool: "analysis_complete",
              message: ok ? "分析完成" : `分析失败: ${error || "未知错误"}`,
              phase: "finalize",
              color: ok ? "green" : "gray",
              status: ok ? "complete" : "error",
            },
          ],
        };});
        break;
      }

      case "done": {
        // Stream sentinel — handled in useAnalysisStream (closes EventSource)
        // Mark as complete if not already
        if (state.pageState === "RUNNING") {
          set({ pageState: "COMPLETE" });
        }
        break;
      }

      case "error": {
        const { message: errMsg } = event.data as { message: string; recoverable: boolean };
        console.error("Analysis error:", errMsg);
        set({ pageState: "COMPLETE" });
        break;
      }

      case "steering": {
        const { message: steerMsg } = event.data as { message: string };
        set((s) => ({
          timeline: [
            ...s.timeline,
            {
              id: `steer-${event.timestamp}`,
              timestamp: event.timestamp,
              tool: "steering",
              message: steerMsg,
              phase: s.currentPhase,
              color: "purple",
              status: "complete",
            },
          ],
        }));
        break;
      }

      case "system": {
        const { message: sysMsg } = event.data as { message: string };
        set((s) => ({
          timeline: [
            ...s.timeline,
            {
              id: `sys-${event.timestamp}`,
              timestamp: event.timestamp,
              tool: "system",
              message: sysMsg,
              phase: s.currentPhase,
              color: "gray",
              status: "complete",
            },
          ],
        }));
        break;
      }

      case "retry": {
        const { attempt, reason } = event.data as { attempt: number; reason: string };
        set((s) => ({
          timeline: [
            ...s.timeline,
            {
              id: `retry-${event.timestamp}`,
              timestamp: event.timestamp,
              tool: "retry",
              message: `重试 #${attempt}: ${reason}`,
              phase: s.currentPhase,
              color: "amber",
              status: "complete",
            },
          ],
        }));
        break;
      }

      case "context_compacted": {
        // Informational only — no state change needed
        break;
      }
    }
  },

  loadSnapshot: (snapshot) => {
    const timeline = [...(snapshot.timeline || [])].sort(
      (a, b) => (a.timestamp || 0) - (b.timestamp || 0)
    );
    set({
      pageState: "COMPLETE",
      isReplay: true,
      resumable: snapshot.resumable ?? false,
      analysisId: snapshot.id,
      analysisQuery: snapshot.query || "",
      reasoningText: snapshot.reasoning_text || "",
      thinkingText: snapshot.thinking_text || "",
      _rawTextBuffer: (snapshot.reasoning_text || "") +
        (snapshot.thinking_text ? `\n<thinking>\n${snapshot.thinking_text}\n</thinking>` : ""),
      timeline,
      dataPanel: snapshot.panels?.data || initialDataPanel,
      modelPanel: snapshot.panels?.model || initialModelPanel,
      compsPanel: snapshot.panels?.comps || initialCompsPanel,
      strategyPanel: snapshot.panels?.strategy || initialStrategyPanel,
      memoryPanel: snapshot.panels?.memory || initialMemoryPanel,
      fundamentalsPanel: snapshot.panels?.fundamentals || initialFundamentalsPanel,
    });
  },

  reset: () => {
    set({
      pageState: "IDLE",
      isReplay: false,
      resumable: false,
      analysisId: null,
      timeline: [],
      reasoningText: "",
      thinkingText: "",
      _rawTextBuffer: "",
      currentPhase: "gather",
      pendingQuestion: null,
      activeTab: "report",
      lastUserTabSwitch: 0,
      dataPanel: initialDataPanel,
      modelPanel: initialModelPanel,
      compsPanel: initialCompsPanel,
      strategyPanel: initialStrategyPanel,
      memoryPanel: initialMemoryPanel,
      fundamentalsPanel: initialFundamentalsPanel,
    });
  },
}));

/**
 * Extract panel data from tool_end results based on tool name.
 * Maps backend ToolResult.data shapes to frontend panel state.
 */
/**
 * Parse <thinking>...</thinking> blocks from complete text.
 *
 * Works on the full accumulated buffer — never on individual SSE chunks —
 * so tags are always intact regardless of how they were chunked by streaming.
 */
function _splitThinkingBlocks(raw: string): { reasoning: string; thinking: string } {
  const OPEN = "<thinking>";
  const CLOSE = "</thinking>";
  const reasoningParts: string[] = [];
  const thinkingParts: string[] = [];

  let pos = 0;
  while (pos < raw.length) {
    const openIdx = raw.indexOf(OPEN, pos);
    if (openIdx === -1) {
      reasoningParts.push(raw.slice(pos));
      break;
    }

    reasoningParts.push(raw.slice(pos, openIdx));

    const closeIdx = raw.indexOf(CLOSE, openIdx + OPEN.length);
    if (closeIdx === -1) {
      // Unclosed block — tag might still be streaming in.
      // Capture what we have so far as in-progress thinking.
      thinkingParts.push(raw.slice(openIdx + OPEN.length));
      break;
    }

    thinkingParts.push(raw.slice(openIdx + OPEN.length, closeIdx));
    pos = closeIdx + CLOSE.length;
  }

  // During streaming, the buffer may end with a partial "<thinking>" or
  // "</thinking>" prefix (e.g. "<thi", "</think") before the full tag has
  // arrived. Strip any such trailing prefix so it never flashes in the UI.
  let reasoning = reasoningParts.join("");
  reasoning = _trimPartialTag(reasoning);

  return {
    reasoning,
    thinking: thinkingParts.join("\n---\n"),
  };
}

/** Remove a trailing partial `<thinking>` or `</thinking>` tag prefix. */
function _trimPartialTag(text: string): string {
  const tags = ["<thinking>", "</thinking>"];
  for (const tag of tags) {
    for (let len = tag.length - 1; len >= 1; len--) {
      if (text.endsWith(tag.slice(0, len))) {
        return text.slice(0, -len);
      }
    }
  }
  return text;
}


function _extractPanelData(
  tool: string,
  result: Record<string, unknown>,
  set: (fn: (s: AnalysisStore) => Partial<AnalysisStore>) => void
) {
  switch (tool) {
    case "valuation": {
      const dcf = (result.dcf as Record<string, unknown>) || result;
      const comps = result.comps as Record<string, unknown> | undefined;
      _extractPanelData("build_dcf", dcf, set);
      if (comps && typeof comps === "object") {
        _extractPanelData("get_comps", comps, set);
      }
      // Extract cross_check and warnings for ModelPanel
      const crossCheck = result.cross_check as Record<string, unknown> | undefined;
      const dcfWarnings = (dcf as Record<string, unknown>)?.warnings as string[] | undefined;
      if (crossCheck || dcfWarnings) {
        set((s) => ({
          modelPanel: {
            ...s.modelPanel,
            crossCheck: crossCheck || s.modelPanel.crossCheck,
            warnings: dcfWarnings || s.modelPanel.warnings,
          },
        }));
      }
      break;
    }

    case "build_dcf": {
      // Backend: {fair_value_per_share, current_price, gap_pct, year_by_year, sensitivity, implied_multiples, ...}
      const fv = result.fair_value_per_share as number | undefined;
      const cp = result.current_price as number | undefined;
      const gap = result.gap_pct as number | undefined;
      const yby = result.year_by_year as Record<string, unknown>[] | undefined;
      const sens = result.sensitivity as Record<string, unknown> | undefined;
      const mult = result.implied_multiples as Record<string, unknown> | undefined;

      // Build sensitivity cells
      const sensCells: import("@/types/analysis").SensitivityCell[] = [];
      let sensRowVals: string[] = [];
      let sensColVals: string[] = [];
      if (sens) {
        const waccVals = (sens.wacc_values as number[]) || [];
        const growthVals = (sens.growth_values as number[]) || [];
        const matrix = (sens.matrix as (number | null)[][]) || [];
        sensRowVals = waccVals.map((v) => `${(v * 100).toFixed(1)}%`);
        sensColVals = growthVals.map((v) => `${(v * 100).toFixed(1)}%`);
        for (let i = 0; i < matrix.length; i++) {
          for (let j = 0; j < (matrix[i]?.length || 0); j++) {
            const val = matrix[i][j];
            if (val != null) {
              sensCells.push({
                row: sensRowVals[i] || "",
                col: sensColVals[j] || "",
                value: val,
                isBase: i === Math.floor(waccVals.length / 2) && j === Math.floor(growthVals.length / 2),
              });
            }
          }
        }
      }

      // Build implied multiples
      const multiples: { label: string; value: string | number }[] = [];
      if (mult) {
        if (mult.fwd_pe != null) multiples.push({ label: "Fwd P/E", value: `${mult.fwd_pe}x` });
        if (mult.ev_ebitda != null) multiples.push({ label: "EV/EBITDA", value: `${mult.ev_ebitda}x` });
        if (mult.fcf_yield != null) multiples.push({ label: "FCF Yield", value: `${((mult.fcf_yield as number) * 100).toFixed(1)}%` });
        if (mult.peg_ratio != null) multiples.push({ label: "PEG", value: `${mult.peg_ratio}x` });
      }

      // Build year-by-year projections
      // DCF returns values in $M; frontend formatNumber expects actual dollars.
      const yearProj: import("@/types/analysis").YearProjection[] = (yby || []).map((row) => ({
        year: `Y${row.year}`,
        revenue: (row.revenue as number) * 1_000_000,
        growth: (row.revenue_growth as number ?? 0) * 100,
        ebitda: (row.ebit as number) * 1_000_000,
        margin: row.revenue ? ((row.ebit as number) / (row.revenue as number)) * 100 : 0,
        fcf: (row.fcf as number) * 1_000_000,
      }));

      set((s) => ({
        modelPanel: {
          ...s.modelPanel,
          fairValue: fv != null ? {
            fairValue: fv,
            currentPrice: cp || 0,
            currency: "USD",
            upside: gap || 0,
            confidence: "medium",
          } : s.modelPanel.fairValue,
          impliedMultiples: multiples.length > 0 ? multiples : s.modelPanel.impliedMultiples,
          sensitivityData: sensCells.length > 0 ? sensCells : s.modelPanel.sensitivityData,
          sensitivityRowValues: sensRowVals.length > 0 ? sensRowVals : s.modelPanel.sensitivityRowValues,
          sensitivityColValues: sensColVals.length > 0 ? sensColVals : s.modelPanel.sensitivityColValues,
          yearByYear: yearProj.length > 0 ? yearProj : s.modelPanel.yearByYear,
          loading: false,
        },
      }));
      break;
    }

    case "get_comps": {
      // Backend: {target, peers: [{ticker, fwd_pe, ev_ebitda, revenue_growth, gross_margin, is_target}], median, target_vs_median}
      const rawPeers = (result.peers as Record<string, unknown>[]) || [];
      const peers: import("@/types/analysis").PeerCompany[] = rawPeers.map((p) => ({
        ticker: (p.ticker as string) || "",
        name: (p.ticker as string) || "",
        marketCap: (p.market_cap as number) || 0,
        peRatio: (p.fwd_pe as number) || 0,
        evEbitda: (p.ev_ebitda as number) || 0,
        revenueGrowth: (p.revenue_growth as number) || 0,
        margin: (p.gross_margin as number) || 0,
        isTarget: Boolean(p.is_target),
      }));
      const scatter: import("@/types/analysis").ScatterPoint[] = rawPeers
        .filter((p) => p.ev_ebitda != null && p.revenue_growth != null)
        .map((p) => ({
          ticker: (p.ticker as string) || "",
          x: (p.ev_ebitda as number) || 0,
          y: ((p.revenue_growth as number) || 0) * 100,
          isTarget: p.is_target as boolean,
        }));

      set((s) => ({
        compsPanel: {
          ...s.compsPanel,
          peers: peers.length > 0 ? peers : s.compsPanel.peers,
          scatterData: scatter.length > 0 ? scatter : s.compsPanel.scatterData,
          loading: false,
        },
      }));
      break;
    }

    case "generate_trade_signal": {
      set((s) => ({
        strategyPanel: {
          ...s.strategyPanel,
          signal: {
            ticker: (result.ticker as string) || "",
            action: (result.action as string) || "WATCH",
            price: typeof result.price === "number" ? result.price : 0,
            targetPrice: typeof result.target_price === "number" ? result.target_price : 0,
            stopLoss: typeof result.stop_loss === "number" ? result.stop_loss : 0,
            positionPct: typeof result.position_pct === "number" ? result.position_pct : 0,
            catalysts: (result.catalysts as string) || "",
            reasoning: (result.reasoning as string) || "",
            suggestedShares: typeof result.suggested_shares === "number" ? result.suggested_shares : 0,
            alreadyHeld: !!result.already_held,
            riskRewardRatio: typeof result.risk_reward_ratio === "number" ? result.risk_reward_ratio : null,
            warnings: Array.isArray(result.warnings) ? result.warnings as string[] : [],
          },
          loading: false,
        },
      }));
      break;
    }

    case "get_portfolio": {
      const positions = Array.isArray(result.positions)
        ? (result.positions as Record<string, unknown>[]).map((position) => ({
            ticker: (position.ticker as string) || "",
            shares: typeof position.shares === "number" ? position.shares : 0,
            avgCost: typeof position.avg_cost === "number" ? position.avg_cost : 0,
            livePrice: typeof position.live_price === "number" ? position.live_price : null,
            marketValue: typeof position.market_value === "number" ? position.market_value : 0,
            unrealizedPnl: typeof position.unrealized_pnl === "number" ? position.unrealized_pnl : 0,
            unrealizedPnlPct:
              typeof position.unrealized_pnl_pct === "number" ? position.unrealized_pnl_pct : 0,
            entryDate: (position.entry_date as string) || null,
          }))
        : [];

      set((s) => ({
        strategyPanel: {
          ...s.strategyPanel,
          portfolio: {
            cash: typeof result.cash === "number" ? result.cash : 0,
            totalMarketValue:
              typeof result.total_market_value === "number" ? result.total_market_value : 0,
            totalPortfolioValue:
              typeof result.total_portfolio_value === "number" ? result.total_portfolio_value : 0,
            totalUnrealizedPnl:
              typeof result.total_unrealized_pnl === "number" ? result.total_unrealized_pnl : 0,
            totalRealizedPnl:
              typeof result.total_realized_pnl === "number" ? result.total_realized_pnl : 0,
            totalReturnPct:
              typeof result.total_return_pct === "number" ? result.total_return_pct : 0,
            positionCount: typeof result.position_count === "number" ? result.position_count : positions.length,
            winLoss: (result.win_loss as string) || "—",
            investedPct: typeof result.invested_pct === "number" ? result.invested_pct : 0,
            positions,
          },
          loading: false,
        },
      }));
      break;
    }

    case "financials":
    case "fmp_get_financials": {
      // Backend: {ticker, statement_type, period, data: [...financial rows...]}
      const stType = result.statement_type as string || "";
      const rawData = (result.data as Record<string, unknown>[]) || [];
      if (rawData.length === 0) break;

      // Convert to FinancialTableData
      const titles: Record<string, string> = {
        "income-statement": "利润表",
        "balance-sheet-statement": "资产负债表",
        "cash-flow-statement": "现金流量表",
        "profile": "公司概况",
        "ratios": "财务比率",
      };

      if (stType === "profile") {
        // Profile is a single object, extract key metrics
        const p = rawData[0] || {};
        const newMetrics: import("@/types/analysis").MetricItem[] = [];
        if (p.price) newMetrics.push({ label: "股价", value: p.price as number, unit: "USD" });
        if (p.mktCap) newMetrics.push({ label: "市值", value: `${((p.mktCap as number) / 1e9).toFixed(1)}B`, unit: "USD" });
        if (p.pe) newMetrics.push({ label: "P/E", value: (p.pe as number).toFixed(1) });
        if (p.beta) newMetrics.push({ label: "Beta", value: (p.beta as number).toFixed(2) });
        if (p.dividendYield) newMetrics.push({ label: "股息率", value: `${((p.dividendYield as number) * 100).toFixed(2)}%` });
        if (newMetrics.length > 0) {
          set((s) => ({
            dataPanel: { ...s.dataPanel, metrics: [...s.dataPanel.metrics, ...newMetrics], loading: false },
          }));
        }
      } else {
        // Financial statement — build a table
        const latest = rawData[0] || {};
        const headers = ["指标", ...rawData.map((r) => (r.calendarYear as string || r.date as string || "").substring(0, 4))];

        // Pick key rows based on statement type
        const keyFields: Record<string, string[]> = {
          "income-statement": ["revenue", "grossProfit", "operatingIncome", "netIncome", "eps", "epsdiluted"],
          "balance-sheet-statement": ["totalAssets", "totalLiabilities", "totalEquity", "cashAndShortTermInvestments", "totalDebt"],
          "cash-flow-statement": ["operatingCashFlow", "capitalExpenditure", "freeCashFlow", "dividendsPaid"],
          "ratios": ["grossProfitMargin", "operatingProfitMargin", "netProfitMargin", "returnOnEquity", "debtEquityRatio"],
        };
        const fieldLabels: Record<string, string> = {
          revenue: "营收", grossProfit: "毛利", operatingIncome: "营业利润", netIncome: "净利润",
          eps: "EPS", epsdiluted: "稀释EPS",
          totalAssets: "总资产", totalLiabilities: "总负债", totalEquity: "股东权益",
          cashAndShortTermInvestments: "现金及短期投资", totalDebt: "总债务",
          operatingCashFlow: "经营现金流", capitalExpenditure: "资本支出", freeCashFlow: "自由现金流", dividendsPaid: "股息支出",
          grossProfitMargin: "毛利率", operatingProfitMargin: "营业利润率", netProfitMargin: "净利率",
          returnOnEquity: "ROE", debtEquityRatio: "负债/权益",
        };
        const fields = keyFields[stType] || Object.keys(latest).filter((k) => typeof latest[k] === "number").slice(0, 8);

        const rows: import("@/types/analysis").FinancialRow[] = fields.map((field) => ({
          label: fieldLabels[field] || field,
          values: rawData.map((r) => {
            const v = r[field];
            if (v == null) return "-";
            if (typeof v === "number") {
              if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
              if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
              if (Math.abs(v) < 1 && v !== 0) return `${(v * 100).toFixed(1)}%`;
              return v.toFixed(1);
            }
            return String(v);
          }),
        }));

        const table: import("@/types/analysis").FinancialTableData = {
          title: `${result.ticker || ""} ${titles[stType] || stType}`,
          headers,
          rows,
        };

        set((s) => ({
          dataPanel: {
            ...s.dataPanel,
            financialTables: [...s.dataPanel.financialTables, table],
            loading: false,
          },
        }));
      }
      break;
    }

    case "quote":
    case "yf_quote": {
      // Backend: {ticker, name, price, market_cap, pe_trailing, pe_forward, ev_ebitda, ...}
      const newMetrics: import("@/types/analysis").MetricItem[] = [];
      const ticker = result.ticker as string || "";
      if (result.price) newMetrics.push({ label: `${ticker} 价格`, value: result.price as number, unit: (result.currency as string) || "USD" });
      if (result.market_cap) newMetrics.push({ label: "市值", value: `$${((result.market_cap as number) / 1e9).toFixed(1)}B` });
      if (result.pe_trailing) newMetrics.push({ label: "P/E (TTM)", value: (result.pe_trailing as number).toFixed(1) });
      if (result.pe_forward) newMetrics.push({ label: "Fwd P/E", value: (result.pe_forward as number).toFixed(1) });
      if (result.ev_ebitda) newMetrics.push({ label: "EV/EBITDA", value: (result.ev_ebitda as number).toFixed(1) });
      if (result.dividend_yield) newMetrics.push({ label: "股息率", value: `${((result.dividend_yield as number) * 100).toFixed(2)}%` });
      if (newMetrics.length > 0) {
        set((s) => ({
          dataPanel: { ...s.dataPanel, metrics: [...s.dataPanel.metrics, ...newMetrics], loading: false },
        }));
      }
      break;
    }

    case "recall":
    case "recall_memory": {
      if (result.total_results || result.content) {
        set((s) => ({
          memoryPanel: {
            ...s.memoryPanel,
            recentRecalls: [
              ...s.memoryPanel.recentRecalls,
              {
                company: (result.subject as string) || (result.company as string) || "?",
                date: new Date().toISOString().split("T")[0],
                relevance: typeof result.total_results === "number" ? Math.min(1, (result.total_results as number) / 10) : 1,
              },
            ],
            loading: false,
          },
        }));
      }
      break;
    }

    case "emit_report": {
      const title = (result.title as string) || "";
      const content = (result.content as string) || "";
      if (content) {
        set(() => ({
          fundamentalsPanel: {
            title,
            content,
            loading: false,
          },
        }));
      }
      break;
    }

    case "check_calibration": {
      set((s) => ({
        memoryPanel: {
          ...s.memoryPanel,
          calibrationHits: typeof result.hits === "number" ? result.hits : s.memoryPanel.calibrationHits,
          calibrationMisses: typeof result.misses === "number" ? result.misses : s.memoryPanel.calibrationMisses,
          loading: false,
        },
      }));
      break;
    }
  }
}
