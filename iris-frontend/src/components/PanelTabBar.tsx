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
  {
    key: "memory",
    label: "记忆",
    iconPath:
      "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4",
    countSelector: (s) => s.memoryPanel.recentRecalls.length,
  },
];

export function PanelTabBar() {
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);

  /* Read all panel counts with shallow comparison to avoid infinite re-renders */
  const counts = useAnalysisStore(
    useShallow((s) => {
      const result: Record<ActiveTab, number> = {
        data: 0,
        model: 0,
        comps: 0,
        memory: 0,
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
    <div className="flex flex-shrink-0 border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
      {TABS.map((tab) => {
        const isActive = activeTab === tab.key;
        const count = counts[tab.key];

        return (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`relative px-[10px] py-[6px] font-mono text-[11px] font-medium cursor-pointer ${
              isActive
                ? "text-[var(--iris-accent)]"
                : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
            }`}
          >
            {/* Label */}
            <span>{tab.label}</span>

            {/* Count badge - tiny inline */}
            {count > 0 && (
              <span className="ml-1 font-mono text-[9px] opacity-60">
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
