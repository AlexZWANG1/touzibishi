"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import type { Phase, PageState } from "@/types/analysis";

const PHASES: { key: Phase; label: string }[] = [
  { key: "gather", label: "收集" },
  { key: "analyze", label: "分析" },
  { key: "evaluate", label: "评估" },
  { key: "finalize", label: "总结" },
];

interface PhaseIndicatorProps {
  compact?: boolean;
}

export function PhaseIndicator({ compact = false }: PhaseIndicatorProps) {
  const currentPhase = useAnalysisStore((s) => s.currentPhase);
  const pageState: PageState = useAnalysisStore((s) => s.pageState);
  const currentIdx = PHASES.findIndex((phase) => phase.key === currentPhase);
  const isComplete = pageState === "COMPLETE";

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {PHASES.map((phase, index) => {
          const active = phase.key === currentPhase && !isComplete;
          const past = isComplete || index < currentIdx;
          return (
            <span
              key={phase.key}
              title={phase.label}
              className="inline-flex h-3 w-3 rounded-full"
              style={{
                background: active ? "var(--ac)" : past ? "var(--bg-3)" : "transparent",
                border: active ? "none" : "1px solid var(--b2)",
              }}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PHASES.map((phase, index) => {
        const active = phase.key === currentPhase && !isComplete;
        const past = isComplete || index < currentIdx;

        return (
          <span
            key={phase.key}
            className={`rounded-pill px-3 py-1.5 text-[11px] font-medium transition-colors ${active ? "animate-[phase-activate_0.25s_ease-out]" : ""}`}
            style={{
              background: active ? "var(--ac-s)" : past ? "var(--bg-2)" : "transparent",
              color: active ? "var(--ac)" : past ? "var(--t2)" : "var(--t4)",
              border: active ? "1px solid var(--ac-m)" : "1px solid transparent",
            }}
          >
            {phase.label}
          </span>
        );
      })}

      <span className="ml-auto rounded-pill bg-[var(--bg-2)] px-3 py-1.5 font-mono text-[10px] text-[var(--t3)]">
        {isComplete
          ? "已完成"
          : pageState === "WAITING"
            ? "等待输入"
            : pageState === "RUNNING"
              ? "运行中"
              : "就绪"}
      </span>
    </div>
  );
}
