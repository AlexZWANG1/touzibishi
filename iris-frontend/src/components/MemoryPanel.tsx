"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";

export function MemoryPanel() {
  const panel = useAnalysisStore((s) => s.memoryPanel);

  if (panel.loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--phase-finalize)] border-t-transparent" />
          <p className="text-sm text-[var(--iris-text-muted)]">加载记忆数据...</p>
        </div>
      </div>
    );
  }

  if (panel.calibrationHits === 0 && panel.calibrationMisses === 0 && panel.recentRecalls.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <svg
            className="mx-auto mb-3 h-10 w-10 text-[var(--iris-text-muted)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
            />
          </svg>
          <p className="text-sm text-[var(--iris-text-muted)]">
            暂无记忆数据
          </p>
          <p className="mt-1 text-xs text-[var(--iris-text-muted)]">
            分析过程中的记忆回忆和校准数据将在此显示
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5">
      <CalibrationSummary
        hits={panel.calibrationHits}
        misses={panel.calibrationMisses}
        recentRecalls={panel.recentRecalls}
      />
    </div>
  );
}
