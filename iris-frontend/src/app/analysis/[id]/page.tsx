"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useShallow } from "zustand/react/shallow";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useAnalysisStream } from "@/hooks/useAnalysisStream";
import { PhaseIndicator } from "@/components/PhaseIndicator";
import { DebugPanel } from "@/components/DebugPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { DataPanel } from "@/components/DataPanel";
import { ModelPanel } from "@/components/ModelPanel";
import { CompsPanel } from "@/components/CompsPanel";
import { StrategyPanel } from "@/components/StrategyPanel";
import { FundamentalsPanel } from "@/components/FundamentalsPanel";
import { PanelTabBar } from "@/components/PanelTabBar";

export default function AnalysisPage() {
  const params = useParams();
  const id = params.id as string;

  const pageState = useAnalysisStore((s) => s.pageState);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const analysisQuery = useAnalysisStore((s) => s.analysisQuery);
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const setActiveTab = useAnalysisStore((s) => s.setActiveTab);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const tabsWithData = useAnalysisStore(
    useShallow((s) => ({
      fundamentals: Boolean(s.fundamentalsPanel.content),
      data: s.dataPanel.metrics.length > 0 || s.dataPanel.financialTables.length > 0,
      model:
        s.modelPanel.fairValue !== null ||
        s.modelPanel.yearByYear.length > 0 ||
        s.modelPanel.impliedMultiples.length > 0,
      comps: s.compsPanel.peers.length > 0 || s.compsPanel.scatterData.length > 0,
      strategy:
        s.strategyPanel.signal !== null ||
        s.strategyPanel.portfolio !== null ||
        s.memoryPanel.calibrationHits > 0 ||
        s.memoryPanel.calibrationMisses > 0,
    })),
  );

  const hasActiveSkillTab =
    activeTab !== "report" && tabsWithData[activeTab as keyof typeof tabsWithData];

  useEffect(() => {
    const { reset } = useAnalysisStore.getState();
    reset();
    useAnalysisStore.setState({ analysisId: id, pageState: "IDLE", activeTab: "report" });
  }, [id]);

  useEffect(() => {
    if (activeTab !== "report" && !tabsWithData[activeTab as keyof typeof tabsWithData]) {
      setActiveTab("report");
    }
  }, [activeTab, setActiveTab, tabsWithData]);

  useAnalysisStream(id);

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col bg-[var(--bg)]">
      {isReplay && (
        <div className="shrink-0 border-b border-[var(--ac-m)] bg-[var(--ac-s)] px-5 py-1.5 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--ac)]">
          历史回看
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside
          className="shrink-0 border-r border-[var(--b2)] bg-[var(--bg-2)] transition-[width] duration-200"
          style={{ width: sidebarCollapsed ? 84 : 280 }}
        >
          <div className="flex h-full flex-col">
            <div className="border-b border-[var(--b1)] px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                {!sidebarCollapsed ? (
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                      Research Query
                    </div>
                    <p className="mt-2 text-[13px] leading-[1.7] text-[var(--t1)]">
                      {analysisQuery || (pageState === "IDLE" ? "正在载入分析上下文..." : "等待查询文本")}
                    </p>
                  </div>
                ) : (
                  <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                    Debug
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
                  className="rounded-md p-2 text-[var(--t3)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--t1)]"
                  aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d={sidebarCollapsed ? "M9 5l7 7-7 7" : "M15 19l-7-7 7-7"} />
                  </svg>
                </button>
              </div>

              <div className="mt-4">
                <PhaseIndicator compact={sidebarCollapsed} />
              </div>
            </div>

            {!sidebarCollapsed ? (
              <div className="min-h-0 flex-1">
                <DebugPanel />
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-center px-2 text-center text-[11px] text-[var(--t4)]">
                Logs
              </div>
            )}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col bg-[rgba(255,255,255,0.55)]">
          <PanelTabBar />

          <div className="min-h-0 flex-1 overflow-hidden">
            {hasActiveSkillTab ? (
              <div className="h-full overflow-y-auto">
                {activeTab === "fundamentals" && <FundamentalsPanel />}
                {activeTab === "data" && <DataPanel />}
                {activeTab === "model" && <ModelPanel />}
                {activeTab === "comps" && <CompsPanel />}
                {activeTab === "strategy" && <StrategyPanel />}
              </div>
            ) : (
              <ChatPanel />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
