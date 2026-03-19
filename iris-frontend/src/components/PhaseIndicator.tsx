"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import type { Phase, PageState } from "@/types/analysis";

const phases: { key: Phase; label: string }[] = [
  { key: "gather", label: "收集" },
  { key: "analyze", label: "分析" },
  { key: "evaluate", label: "评估" },
  { key: "finalize", label: "总结" },
];

export function PhaseIndicator() {
  const currentPhase = useAnalysisStore((s) => s.currentPhase);
  const pageState: PageState = useAnalysisStore((s) => s.pageState);
  const currentIdx = phases.findIndex((p) => p.key === currentPhase);
  const isComplete = pageState === "COMPLETE";

  return (
    <div
      className="flex items-center font-mono"
      style={{
        height: 28,
        padding: "4px 10px",
        borderBottom: "1px solid var(--iris-border)",
      }}
    >
      <div className="flex items-center gap-0">
        {phases.map((phase, idx) => {
          const isActive = phase.key === currentPhase && !isComplete;
          const isPast = idx < currentIdx || isComplete;

          return (
            <div key={phase.key} className="flex items-center">
              {idx > 0 && (
                <span
                  className="mx-0.5"
                  style={{
                    fontSize: 10,
                    color: "var(--iris-text-muted)",
                    opacity: 0.4,
                  }}
                >
                  ›
                </span>
              )}
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  color: isActive
                    ? "var(--iris-accent)"
                    : isPast
                      ? "var(--iris-text-secondary)"
                      : "var(--iris-text-muted)",
                  opacity: isActive ? 1 : isPast ? 0.7 : 0.3,
                }}
              >
                {phase.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Status on the right */}
      <div className="ml-auto flex items-center">
        {isComplete && (
          <span
            className="font-mono"
            style={{ fontSize: 10, color: "var(--iris-data)", fontWeight: 500 }}
          >
            完成
          </span>
        )}
        {pageState === "RUNNING" && (
          <span
            className="font-mono"
            style={{ fontSize: 10, color: "var(--iris-accent)", fontWeight: 500 }}
          >
            运行中
          </span>
        )}
        {pageState === "WAITING" && (
          <span
            className="font-mono"
            style={{ fontSize: 10, color: "var(--iris-accent)", fontWeight: 500 }}
          >
            等待输入
          </span>
        )}
      </div>
    </div>
  );
}
