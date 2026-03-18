"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import type { ActiveTab } from "@/types/analysis";

const tabs: { key: ActiveTab; label: string; icon: string }[] = [
  { key: "data", label: "数据", icon: "M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
  { key: "model", label: "模型", icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" },
  { key: "comps", label: "可比", icon: "M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" },
  { key: "memory", label: "记忆", icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" },
];

export function PanelTabBar() {
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);

  return (
    <div className="flex border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => setActiveTab(tab.key)}
          className={`relative flex items-center gap-1.5 px-5 py-3 text-sm font-medium transition-colors ${
            activeTab === tab.key
              ? "text-[var(--iris-accent)]"
              : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={tab.icon} />
          </svg>
          {tab.label}
          {activeTab === tab.key && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--iris-accent)]" />
          )}
        </button>
      ))}
    </div>
  );
}
