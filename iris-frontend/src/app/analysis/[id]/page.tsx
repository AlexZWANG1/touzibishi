"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useAnalysisStream } from "@/hooks/useAnalysisStream";
import { PhaseIndicator } from "@/components/PhaseIndicator";
import { StreamingTimeline } from "@/components/StreamingTimeline";
import { ReportPanel } from "@/components/AIReasoningArea";
import { SteeringInput } from "@/components/SteeringInput";
import { PendingQuestionCard } from "@/components/PendingQuestionCard";
import { PanelTabBar } from "@/components/PanelTabBar";
import { DataPanel } from "@/components/DataPanel";
import { ModelPanel } from "@/components/ModelPanel";
import { CompsPanel } from "@/components/CompsPanel";

export default function AnalysisPage() {
  const params = useParams();
  const id = params.id as string;

  const pageState = useAnalysisStore((s) => s.pageState);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const analysisQuery = useAnalysisStore((s) => s.analysisQuery);
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);

  useEffect(() => {
    useAnalysisStore.setState({ analysisId: id, pageState: "RUNNING" });
  }, [id]);

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
        {/* Left Panel - fixed 320px log panel */}
        <div className="flex w-[320px] shrink-0 flex-col border-r border-[var(--iris-border)]">
          {/* Query display */}
          {analysisQuery && (
            <div className="shrink-0 border-b border-[var(--iris-border)] px-[10px] py-[6px]">
              <p className="font-mono text-[12px] text-[var(--iris-text)] truncate">
                <span className="text-[var(--iris-accent)] mr-1.5">&gt;</span>
                {analysisQuery}
              </p>
            </div>
          )}
          {/* Phase Indicator */}
          <div className="shrink-0 border-b border-[var(--iris-border)] px-[8px] py-[4px]">
            <PhaseIndicator />
          </div>

          {/* Timeline - scrollable center */}
          <div className="min-h-0 flex-1 overflow-y-auto px-[6px] py-[4px]">
            {pageState === "IDLE" ? (
              <div className="flex h-full items-center justify-center">
                <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
                  WAITING...
                </p>
              </div>
            ) : (
              <StreamingTimeline />
            )}
          </div>

          {/* Left panel bottom spacer */}
        </div>

        {/* Right Panel - flex-1 */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Tab Bar */}
          <PanelTabBar />

          {/* Panel Content */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {pageState === "IDLE" ? (
              <div className="flex h-full items-center justify-center">
                <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
                  LOADING PANELS...
                </p>
              </div>
            ) : (
              <>
                {activeTab === "report" && <ReportPanel />}
                {activeTab === "data" && <DataPanel />}
                {activeTab === "model" && <ModelPanel />}
                {activeTab === "comps" && <CompsPanel />}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: Steering Input / Pending Question */}
      <div className="shrink-0 border-t border-[var(--iris-border)] p-[6px_10px] bg-[var(--iris-bg)]">
        {pageState === "WAITING" && pendingQuestion ? (
          <PendingQuestionCard />
        ) : !isReplay ? (
          <SteeringInput />
        ) : null}
      </div>
    </div>
  );
}
