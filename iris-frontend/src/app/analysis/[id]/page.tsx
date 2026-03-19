"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { useAnalysisStream } from "@/hooks/useAnalysisStream";
import { PhaseIndicator } from "@/components/PhaseIndicator";
import { StreamingTimeline } from "@/components/StreamingTimeline";
import { AIReasoningArea } from "@/components/AIReasoningArea";
import { SteeringInput } from "@/components/SteeringInput";
import { PendingQuestionCard } from "@/components/PendingQuestionCard";
import { PanelTabBar } from "@/components/PanelTabBar";
import { DataPanel } from "@/components/DataPanel";
import { ModelPanel } from "@/components/ModelPanel";
import { CompsPanel } from "@/components/CompsPanel";
import { MemoryPanel } from "@/components/MemoryPanel";

export default function AnalysisPage() {
  const params = useParams();
  const id = params.id as string;

  const pageState = useAnalysisStore((s) => s.pageState);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);

  useEffect(() => {
    useAnalysisStore.setState({ analysisId: id, pageState: "RUNNING" });
  }, [id]);

  useAnalysisStream(id);

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] flex-col bg-[var(--iris-bg)]">
      {/* Replay banner */}
      {isReplay && (
        <div
          className="flex-shrink-0 px-3 py-1 text-[11px] border-b"
          style={{
            borderColor: "var(--iris-accent)",
            color: "var(--iris-accent)",
            background: "rgba(201,168,76,0.05)",
          }}
        >
          历史回看
        </div>
      )}
      {/* Main content area */}
      <div className="flex min-h-0 flex-1">
        {/* Left Panel - fixed 360px log panel */}
        <div className="flex w-[360px] flex-shrink-0 flex-col border-r border-[var(--iris-border)]">
          {/* Phase Indicator */}
          <div className="flex-shrink-0 border-b border-[var(--iris-border)] px-3 py-1">
            <PhaseIndicator />
          </div>

          {/* Timeline - scrollable center */}
          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-1">
            {pageState === "IDLE" ? (
              <div className="flex h-full items-center justify-center">
                <p
                  className="text-[var(--iris-text-muted)]"
                  style={{ fontSize: 11 }}
                >
                  等待初始化...
                </p>
              </div>
            ) : (
              <StreamingTimeline />
            )}
          </div>

          {/* AI Reasoning - bottom, expandable, max 40% height */}
          <div
            className="flex-shrink-0 border-t border-[var(--iris-border)]"
            style={{ maxHeight: "40%" }}
          >
            <AIReasoningArea />
          </div>
        </div>

        {/* Right Panel - flex-1 */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Tab Bar */}
          <PanelTabBar />

          {/* Panel Content */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {pageState === "IDLE" ? (
              <div className="flex h-full items-center justify-center">
                <p
                  className="text-[var(--iris-text-muted)]"
                  style={{ fontSize: 11 }}
                >
                  准备分析面板...
                </p>
              </div>
            ) : (
              <>
                {activeTab === "data" && <DataPanel />}
                {activeTab === "model" && <ModelPanel />}
                {activeTab === "comps" && <CompsPanel />}
                {activeTab === "memory" && <MemoryPanel />}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: Steering Input / Pending Question - solid background */}
      <div
        className="flex-shrink-0 border-t border-[var(--iris-border)] px-3 py-2"
        style={{ background: "var(--iris-bg)" }}
      >
        {pageState === "WAITING" && pendingQuestion ? (
          <PendingQuestionCard />
        ) : !isReplay ? (
          <SteeringInput />
        ) : null}
      </div>
    </div>
  );
}
