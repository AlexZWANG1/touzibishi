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
} from "@/types/analysis";
import type { SSEEvent } from "@/types/api";
import { translateToolStart, TOOL_TAB_MAP } from "@/utils/eventTranslator";
import * as api from "@/utils/api";

interface AnalysisStore {
  pageState: PageState;
  analysisId: string | null;
  timeline: TimelineEvent[];
  reasoningText: string;
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
  analysisId: null,
  timeline: [],
  reasoningText: "",
  currentPhase: "gather",
  pendingQuestion: null,
  activeTab: "data",
  lastUserTabSwitch: 0,
  dataPanel: initialDataPanel,
  modelPanel: initialModelPanel,
  compsPanel: initialCompsPanel,
  memoryPanel: initialMemoryPanel,

  startAnalysis: async (query: string, contextDocs?: string[]) => {
    set({ pageState: "RUNNING", timeline: [], reasoningText: "", currentPhase: "gather" });
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
          set((s) => ({ reasoningText: s.reasoningText + content }));
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

  reset: () => {
    set({
      pageState: "IDLE",
      analysisId: null,
      timeline: [],
      reasoningText: "",
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
 */
function _extractPanelData(
  tool: string,
  result: Record<string, unknown>,
  set: (fn: (s: AnalysisStore) => Partial<AnalysisStore>) => void
) {
  switch (tool) {
    case "build_dcf": {
      // DCF result contains fair_value, assumptions, sensitivity_matrix, etc.
      set((s) => ({
        modelPanel: {
          ...s.modelPanel,
          fairValue: result.fair_value != null
            ? {
                fairValue: result.fair_value as number,
                currentPrice: (result.market_price as number) || 0,
                currency: "USD",
                upside: result.upside != null ? (result.upside as number) : 0,
                confidence: "medium",
              }
            : s.modelPanel.fairValue,
          assumptions: Array.isArray(result.assumptions) ? result.assumptions : s.modelPanel.assumptions,
          impliedMultiples: Array.isArray(result.implied_multiples) ? result.implied_multiples : s.modelPanel.impliedMultiples,
          sensitivityData: Array.isArray(result.sensitivity_matrix) ? result.sensitivity_matrix : s.modelPanel.sensitivityData,
          yearByYear: Array.isArray(result.year_by_year) ? result.year_by_year : s.modelPanel.yearByYear,
          loading: false,
        },
      }));
      break;
    }

    case "get_comps": {
      set((s) => ({
        compsPanel: {
          ...s.compsPanel,
          peers: Array.isArray(result.peers) ? result.peers : s.compsPanel.peers,
          scatterData: Array.isArray(result.scatter) ? result.scatter : s.compsPanel.scatterData,
          loading: false,
        },
      }));
      break;
    }

    case "fmp_get_financials":
    case "fred_get_macro": {
      set((s) => ({
        dataPanel: {
          ...s.dataPanel,
          metrics: Array.isArray(result.metrics) ? result.metrics : s.dataPanel.metrics,
          financialTables: Array.isArray(result.tables) ? result.tables : s.dataPanel.financialTables,
          loading: false,
        },
      }));
      break;
    }

    case "recall_memory":
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
