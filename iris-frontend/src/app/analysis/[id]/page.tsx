"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useAnalysisStream } from "@/hooks/useAnalysisStream";
import { useShallow } from "zustand/react/shallow";
import { PhaseIndicator } from "@/components/PhaseIndicator";
import { DebugPanel } from "@/components/DebugPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { DataPanel } from "@/components/DataPanel";
import { ModelPanel } from "@/components/ModelPanel";
import { CompsPanel } from "@/components/CompsPanel";
import type { ActiveTab } from "@/types/analysis";

/**
 * Skill tabs — only shown when they have data.
 * These appear as small pills above the chat when relevant.
 */
const SKILL_TABS: { key: ActiveTab; label: string }[] = [
  { key: "data", label: "数据" },
  { key: "model", label: "模型" },
  { key: "comps", label: "可比" },
];

export default function AnalysisPage() {
  const params = useParams();
  const id = params.id as string;

  const pageState = useAnalysisStore((s) => s.pageState);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const analysisQuery = useAnalysisStore((s) => s.analysisQuery);
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);

  // Check which skill tabs have data
  const tabsWithData = useAnalysisStore(
    useShallow((s) => ({
      data:
        s.dataPanel.metrics.length > 0 ||
        s.dataPanel.financialTables.length > 0,
      model:
        s.modelPanel.fairValue !== null || s.modelPanel.yearByYear.length > 0,
      comps: s.compsPanel.peers.length > 0,
    }))
  );

  const visibleSkillTabs = SKILL_TABS.filter((t) => tabsWithData[t.key as keyof typeof tabsWithData]);
  const hasActiveSkillTab = activeTab !== "report" && visibleSkillTabs.some((t) => t.key === activeTab);

  useEffect(() => {
    const { reset } = useAnalysisStore.getState();
    reset();
    useAnalysisStore.setState({ analysisId: id, pageState: "IDLE", activeTab: "report" });
  }, [id]);

  useEffect(() => {
    if (activeTab !== "report" && !visibleSkillTabs.some((tab) => tab.key === activeTab)) {
      setActiveTab("report");
    }
  }, [activeTab, setActiveTab, visibleSkillTabs]);

  useAnalysisStream(id);

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden bg-[var(--iris-bg)]">
      {/* Replay banner */}
      {isReplay && (
        <div
          className="shrink-0 px-[10px] py-[3px] font-mono text-[11px] uppercase tracking-wider border-b border-[var(--iris-accent)]"
          style={{
            color: "var(--iris-accent)",
            background: "rgba(245,128,37,0.05)",
          }}
        >
          REPLAY // 历史回看
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Panel — Debug: logs / thinking / memory */}
        <div className="flex w-[300px] shrink-0 flex-col border-r border-[var(--iris-border)] bg-[var(--iris-surface)]">
          {/* Query + Phase header */}
          {analysisQuery && (
            <div className="shrink-0 border-b border-[var(--iris-border)] px-[10px] py-[6px]">
              <p className="font-mono text-[12px] text-[var(--iris-text)] truncate">
                <span className="text-[var(--iris-accent)] mr-1.5">&gt;</span>
                {analysisQuery}
              </p>
            </div>
          )}
          <div className="shrink-0 border-b border-[var(--iris-border)] px-[8px] py-[4px]">
            <PhaseIndicator />
          </div>

          {/* Debug tabs content */}
          <div className="flex-1 min-h-0">
            <DebugPanel />
          </div>
        </div>

        {/* Right Panel — Chat + conditional skill panels */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Skill tab pills — only shown when skills produce data */}
          {visibleSkillTabs.length > 0 && (
            <div
              className="flex-shrink-0 flex items-center gap-1 border-b border-[var(--iris-border)]"
              style={{ padding: "6px 24px" }}
            >
              {/* Chat tab (always first, default) */}
              <button
                onClick={() => setActiveTab("report")}
                className="font-mono transition-colors"
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  padding: "4px 12px",
                  borderRadius: "6px",
                  border: "none",
                  cursor: "pointer",
                  background:
                    activeTab === "report"
                      ? "var(--iris-accent)"
                      : "transparent",
                  color:
                    activeTab === "report"
                      ? "#fff"
                      : "var(--iris-text-secondary)",
                }}
              >
                对话
              </button>

              {/* Skill tabs */}
              {visibleSkillTabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className="font-mono transition-colors"
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    padding: "4px 12px",
                    borderRadius: "6px",
                    border: "none",
                    cursor: "pointer",
                    background:
                      activeTab === tab.key
                        ? "var(--iris-accent)"
                        : "transparent",
                    color:
                      activeTab === tab.key
                        ? "#fff"
                        : "var(--iris-text-secondary)",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Panel content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {hasActiveSkillTab ? (
              <div className="h-full overflow-y-auto">
                {activeTab === "data" && <DataPanel />}
                {activeTab === "model" && <ModelPanel />}
                {activeTab === "comps" && <CompsPanel />}
              </div>
            ) : (
              <ChatPanel />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
