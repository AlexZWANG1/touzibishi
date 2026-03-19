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
  MemoryPanelState,
  AnalysisSnapshot,
} from "@/types/analysis";
import type { SSEEvent } from "@/types/api";
import { translateToolStart, TOOL_TAB_MAP } from "@/utils/eventTranslator";
import * as api from "@/utils/api";

interface AnalysisStore {
  pageState: PageState;
  isReplay: boolean;
  analysisId: string | null;
  timeline: TimelineEvent[];
  reasoningText: string;
  thinkingText: string;
  _inThinkingBlock: boolean;
  currentPhase: Phase;
  pendingQuestion: PendingQuestion | null;
  activeTab: ActiveTab;
  lastUserTabSwitch: number;
  dataPanel: DataPanelState;
  modelPanel: ModelPanelState;
  compsPanel: CompsPanelState;
  memoryPanel: MemoryPanelState;

  startAnalysis: (query: string, contextDocs?: string[]) => Promise<void>;
  sendSteering: (message: string) => Promise<void>;
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

const initialMemoryPanel: MemoryPanelState = {
  calibrationHits: 0,
  calibrationMisses: 0,
  recentRecalls: [],
  loading: false,
};

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  pageState: "IDLE",
  isReplay: false,
  analysisId: null,
  timeline: [],
  reasoningText: "",
  thinkingText: "",
  _inThinkingBlock: false,
  currentPhase: "gather",
  pendingQuestion: null,
  activeTab: "data",
  lastUserTabSwitch: 0,
  dataPanel: initialDataPanel,
  modelPanel: initialModelPanel,
  compsPanel: initialCompsPanel,
  memoryPanel: initialMemoryPanel,

  startAnalysis: async (query: string, contextDocs?: string[]) => {
    set({ pageState: "RUNNING", timeline: [], reasoningText: "", thinkingText: "", _inThinkingBlock: false, currentPhase: "gather" });
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
        const { message, phase, color } = translateToolStart(tool, args || {});
        // Backend doesn't send call_id, so we generate one client-side
        const id = `tool-${tool}-${event.timestamp}`;
        set((s) => ({
          currentPhase: phase,
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

        // Auto-switch tab if user hasn't manually switched in last 5 seconds
        const tabTarget = TOOL_TAB_MAP[tool];
        if (tabTarget && Date.now() - state.lastUserTabSwitch > 5000) {
          set({ activeTab: tabTarget as ActiveTab });
        }

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
            // Stream-aware state machine for <thinking> blocks
            let inThinking = s._inThinkingBlock;
            let thinkingBuf = s.thinkingText;
            let reasoningBuf = s.reasoningText;

            // Check for tag transitions within this chunk
            const openIdx = content.indexOf("<thinking>");
            const closeIdx = content.indexOf("</thinking>");

            if (openIdx !== -1 && closeIdx !== -1 && closeIdx > openIdx) {
              // Both open and close in same chunk
              const before = content.slice(0, openIdx);
              const inside = content.slice(openIdx + 10, closeIdx);
              const after = content.slice(closeIdx + 12);
              if (before) reasoningBuf += before;
              if (inside) thinkingBuf += inside + "\n---\n";
              if (after) reasoningBuf += after;
              inThinking = false;
            } else if (openIdx !== -1) {
              // Entering thinking block
              const before = content.slice(0, openIdx);
              const after = content.slice(openIdx + 10);
              if (before) reasoningBuf += before;
              if (after) thinkingBuf += after;
              inThinking = true;
            } else if (closeIdx !== -1) {
              // Exiting thinking block
              const before = content.slice(0, closeIdx);
              const after = content.slice(closeIdx + 12);
              if (before) thinkingBuf += before;
              thinkingBuf += "\n---\n";
              if (after) reasoningBuf += after;
              inThinking = false;
            } else {
              // No tags — route based on current state
              if (inThinking) {
                thinkingBuf += content;
              } else {
                reasoningBuf += content;
              }
            }

            return {
              reasoningText: reasoningBuf,
              thinkingText: thinkingBuf,
              _inThinkingBlock: inThinking,
            };
          });
        }
        break;
      }

      case "text": {
        const content = event.data.content as string;
        if (content) {
          set({ reasoningText: content });
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
        set((s) => ({
          pageState: "COMPLETE",
          reasoningText: ok && reply ? reply : s.reasoningText,
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
        }));
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
    set({
      pageState: "COMPLETE",
      isReplay: true,
      analysisId: snapshot.id,
      reasoningText: snapshot.reasoning_text || "",
      thinkingText: snapshot.thinking_text || "",
      timeline: snapshot.timeline || [],
      dataPanel: snapshot.panels?.data || initialDataPanel,
      modelPanel: snapshot.panels?.model || initialModelPanel,
      compsPanel: snapshot.panels?.comps || initialCompsPanel,
      memoryPanel: snapshot.panels?.memory || initialMemoryPanel,
    });
  },

  reset: () => {
    set({
      pageState: "IDLE",
      isReplay: false,
      analysisId: null,
      timeline: [],
      reasoningText: "",
      thinkingText: "",
      _inThinkingBlock: false,
      currentPhase: "gather",
      pendingQuestion: null,
      activeTab: "data",
      lastUserTabSwitch: 0,
      dataPanel: initialDataPanel,
      modelPanel: initialModelPanel,
      compsPanel: initialCompsPanel,
      memoryPanel: initialMemoryPanel,
    });
  },
}));

/**
 * Extract panel data from tool_end results based on tool name.
 * Maps backend ToolResult.data shapes to frontend panel state.
 */
function _extractPanelData(
  tool: string,
  result: Record<string, unknown>,
  set: (fn: (s: AnalysisStore) => Partial<AnalysisStore>) => void
) {
  switch (tool) {
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
      const yearProj: import("@/types/analysis").YearProjection[] = (yby || []).map((row) => ({
        year: `Y${row.year}`,
        revenue: row.revenue as number,
        growth: 0,
        ebitda: row.ebit as number,
        margin: row.revenue ? ((row.ebit as number) / (row.revenue as number)) * 100 : 0,
        fcf: row.fcf as number,
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
        marketCap: 0,
        peRatio: (p.fwd_pe as number) || 0,
        evEbitda: (p.ev_ebitda as number) || 0,
        revenueGrowth: (p.revenue_growth as number) || 0,
        margin: (p.gross_margin as number) || 0,
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

    case "recall_memory": {
      if (result.content) {
        set((s) => ({
          memoryPanel: {
            ...s.memoryPanel,
            recentRecalls: [
              ...s.memoryPanel.recentRecalls,
              { company: (result.company as string) || "?", date: new Date().toISOString().split("T")[0], relevance: 1 },
            ],
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
