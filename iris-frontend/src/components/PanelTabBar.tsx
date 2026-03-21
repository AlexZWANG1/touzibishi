"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useShallow } from "zustand/react/shallow";
import type { ActiveTab } from "@/types/analysis";

const TABS: { key: ActiveTab; label: string }[] = [
  { key: "report", label: "对话" },
  { key: "fundamentals", label: "研究" },
  { key: "data", label: "数据" },
  { key: "model", label: "模型" },
  { key: "comps", label: "可比" },
  { key: "strategy", label: "策略" },
];

export function PanelTabBar() {
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);
  const state = useAnalysisStore(
    useShallow((s) => ({
      hasReasoning: Boolean(s.reasoningText?.trim()),
      fundamentalsCount: s.fundamentalsPanel.sections.length,
      dataCount: s.dataPanel.metrics.length + s.dataPanel.financialTables.length,
      modelCount:
        (s.modelPanel.fairValue ? 1 : 0) +
        s.modelPanel.impliedMultiples.length +
        s.modelPanel.yearByYear.length,
      compsCount: s.compsPanel.peers.length + s.compsPanel.scatterData.length,
      strategyCount:
        (s.strategyPanel.signal ? 1 : 0) +
        (s.strategyPanel.portfolio ? 1 : 0) +
        (s.memoryPanel.calibrationHits > 0 || s.memoryPanel.calibrationMisses > 0 ? 1 : 0),
    })),
  );

  const counts: Record<ActiveTab, number> = {
    report: state.hasReasoning ? 1 : 0,
    fundamentals: state.fundamentalsCount,
    data: state.dataCount,
    model: state.modelCount,
    comps: state.compsCount,
    strategy: state.strategyCount,
  };

  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-[var(--b2)] bg-[rgba(255,255,255,0.7)] px-5 py-3 backdrop-blur sm:px-7">
      {TABS.map((tab) => {
        const count = counts[tab.key];
        const enabled = tab.key === "report" || count > 0;
        const active = activeTab === tab.key;

        return (
          <button
            key={tab.key}
            type="button"
            disabled={!enabled}
            data-active={active}
            onClick={() => enabled && setActiveTab(tab.key)}
            className="prism-pill-tab disabled:cursor-not-allowed disabled:opacity-45"
          >
            <span>{tab.label}</span>
            {count > 0 && (
              <span
                className="rounded-pill px-1.5 py-0.5 font-mono text-[10px]"
                style={{
                  background: active ? "rgba(255,255,255,0.2)" : "var(--bg-2)",
                  color: active ? "#ffffff" : "var(--t3)",
                }}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
