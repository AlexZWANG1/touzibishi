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
  const activeTab = useAnalysisStore((s) => s.activeTab);
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);

  useEffect(() => {
    useAnalysisStore.setState({ analysisId: id, pageState: "RUNNING" });
  }, [id]);

  useAnalysisStream(id);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:flex-row">
      {/* Left Panel - 45% */}
      <div className="flex w-full flex-col border-r border-[var(--iris-border)] lg:w-[45%]">
        {/* Phase Indicator */}
        <div className="border-b border-[var(--iris-border)] px-5 py-3">
          <PhaseIndicator />
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <StreamingTimeline />
        </div>

        {/* AI Reasoning */}
        <div className="border-t border-[var(--iris-border)]">
          <AIReasoningArea />
        </div>

        {/* Steering / Question */}
        <div className="border-t border-[var(--iris-border)] px-5 py-4">
          {pageState === "WAITING" && pendingQuestion ? (
            <PendingQuestionCard />
          ) : (
            <SteeringInput />
          )}
        </div>
      </div>

      {/* Right Panel - 55% */}
      <div className="flex w-full flex-col lg:w-[55%]">
        {/* Tab Bar */}
        <PanelTabBar />

        {/* Panel Content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === "data" && <DataPanel />}
          {activeTab === "model" && <ModelPanel />}
          {activeTab === "comps" && <CompsPanel />}
          {activeTab === "memory" && <MemoryPanel />}
        </div>
      </div>
    </div>
  );
}
