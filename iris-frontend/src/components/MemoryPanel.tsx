"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";

export function MemoryPanel() {
  const panel = useAnalysisStore((s) => s.memoryPanel);

  if (panel.loading) {
    return (
      <div className="px-[8px] py-[10px] font-mono text-[11px] text-[var(--iris-text-muted)]">
        加载记忆数据...
      </div>
    );
  }

  if (panel.calibrationHits === 0 && panel.calibrationMisses === 0 && panel.recentRecalls.length === 0) {
    return (
      <div className="px-[8px] py-[10px] font-mono text-[11px] text-[var(--iris-text-muted)]">
        暂无记忆数据
      </div>
    );
  }

  return (
    <div className="p-[6px]">
      <CalibrationSummary
        hits={panel.calibrationHits}
        misses={panel.calibrationMisses}
        recentRecalls={panel.recentRecalls}
      />
    </div>
  );
}
