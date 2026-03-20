"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useShallow } from "zustand/react/shallow";
import type { ActiveTab } from "@/types/analysis";

/* Minimal SVG icon paths for each tab */
const TABS: {
  key: ActiveTab;
  label: string;
  iconPath: string;
  countSelector?: (s: ReturnType<typeof useAnalysisStore.getState>) => number;
}[] = [
  {
    key: "report",
    label: "报告",
    iconPath:
      "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    countSelector: (s) => (s.reasoningText ? 1 : 0),
  },
  {
    key: "data",
    label: "数据",
    iconPath:
      "M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z",
    countSelector: (s) =>
      s.dataPanel.metrics.length + s.dataPanel.financialTables.length,
  },
  {
    key: "model",
    label: "模型",
    iconPath:
      "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z",
    countSelector: (s) =>
      (s.modelPanel.fairValue ? 1 : 0) + s.modelPanel.yearByYear.length,
  },
  {
    key: "comps",
    label: "可比",
    iconPath:
      "M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    countSelector: (s) => s.compsPanel.peers.length,
  },
];

export function PanelTabBar() {
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);

  /* Read all panel counts with shallow comparison to avoid infinite re-renders */
  const counts = useAnalysisStore(
    useShallow((s) => {
      const result: Record<ActiveTab, number> = {
        report: 0,
        data: 0,
        model: 0,
        comps: 0,
      };
      for (const tab of TABS) {
        if (tab.countSelector) {
          result[tab.key] = tab.countSelector(s);
        }
      }
      return result;
    })
  );

  return (
    <div className="flex flex-shrink-0 gap-[4px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
      {TABS.map((tab) => {
        const isActive = activeTab === tab.key;
        const count = counts[tab.key];

        return (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`relative px-[18px] py-[8px] font-mono text-[13px] font-medium cursor-pointer ${
              isActive
                ? "text-[var(--iris-accent)]"
                : "text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)]"
            }`}
          >
            {/* Label */}
            <span>{tab.label}</span>

            {/* Count badge - tiny inline */}
            {count > 0 && (
              <span className="ml-1 font-mono text-[10px] opacity-60">
                {count}
              </span>
            )}

            {/* 1px orange bottom border for active tab */}
            {isActive && (
              <div
                className="absolute bottom-0 left-0 right-0 h-[1px] bg-[var(--iris-accent)]"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
