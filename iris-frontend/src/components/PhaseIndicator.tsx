"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import type { Phase } from "@/types/analysis";

const phases: { key: Phase; label: string; color: string }[] = [
  { key: "gather", label: "收集", color: "var(--phase-gather)" },
  { key: "analyze", label: "分析", color: "var(--phase-analyze)" },
  { key: "evaluate", label: "评估", color: "var(--phase-evaluate)" },
  { key: "finalize", label: "总结", color: "var(--phase-finalize)" },
];

export function PhaseIndicator() {
  const currentPhase = useAnalysisStore((s) => s.currentPhase);
  const pageState = useAnalysisStore((s) => s.pageState);
  const currentIdx = phases.findIndex((p) => p.key === currentPhase);

  return (
    <div className="flex items-center gap-2">
      {phases.map((phase, idx) => {
        const isActive = phase.key === currentPhase;
        const isPast = idx < currentIdx;
        const isComplete = pageState === "COMPLETE";

        return (
          <div key={phase.key} className="flex items-center gap-2">
            {idx > 0 && (
              <div
                className="h-px w-6"
                style={{
                  background: isPast || isComplete ? phase.color : "var(--iris-border)",
                }}
              />
            )}
            <div className="flex items-center gap-1.5">
              <div
                className={`h-2.5 w-2.5 rounded-full transition-all ${
                  isActive && !isComplete ? "pulse-dot" : ""
                }`}
                style={{
                  background:
                    isPast || isActive || isComplete ? phase.color : "var(--iris-border)",
                  boxShadow:
                    isActive && !isComplete ? `0 0 8px ${phase.color}60` : "none",
                }}
              />
              <span
                className="text-xs font-medium transition-colors"
                style={{
                  color:
                    isPast || isActive || isComplete
                      ? phase.color
                      : "var(--iris-text-muted)",
                }}
              >
                {phase.label}
              </span>
            </div>
          </div>
        );
      })}

      {pageState === "COMPLETE" && (
        <div className="ml-auto flex items-center gap-1.5">
          <svg className="h-4 w-4 text-[var(--phase-gather)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-xs font-medium text-[var(--phase-gather)]">完成</span>
        </div>
      )}

      {pageState === "WAITING" && (
        <div className="ml-auto flex items-center gap-1.5">
          <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--event-user)]" />
          <span className="text-xs font-medium text-[var(--event-user)]">等待输入</span>
        </div>
      )}
    </div>
  );
}
