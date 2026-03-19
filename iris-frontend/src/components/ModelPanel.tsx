"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { FairValueCard } from "./FairValueCard";
import { ImpliedMultiples } from "./ImpliedMultiples";
import { SensitivityHeatmap } from "./SensitivityHeatmap";
import { YearByYearTable } from "./YearByYearTable";

function LoadingSkeleton() {
  return (
    <div className="space-y-[6px] p-[6px]">
      <div className="h-20 bg-[var(--iris-surface)]" />
      <div className="h-6 w-2/3 bg-[var(--iris-surface)]" />
      <div className="h-36 bg-[var(--iris-surface)]" />
      <div className="h-48 bg-[var(--iris-surface)]" />
    </div>
  );
}

export function ModelPanel() {
  const panel = useAnalysisStore((s) => s.modelPanel);

  if (panel.loading) {
    return <LoadingSkeleton />;
  }

  if (!panel.fairValue && panel.yearByYear.length === 0 && panel.impliedMultiples.length === 0) {
    return (
      <div className="px-[8px] py-[10px]">
        <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
          等待 DCF 模型构建...
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[10px] p-[6px]">
      {/* Fair Value Card */}
      {panel.fairValue && <FairValueCard data={panel.fairValue} />}

      {/* Implied Multiples row */}
      {panel.impliedMultiples.length > 0 && (
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-[var(--iris-text-muted)] mb-[2px]">
            Implied Multiples
          </p>
          <ImpliedMultiples multiples={panel.impliedMultiples} />
        </div>
      )}

      {/* Year-by-Year Projections */}
      {panel.yearByYear.length > 0 && (
        <YearByYearTable data={panel.yearByYear} />
      )}

      {/* Sensitivity Heatmap */}
      {panel.sensitivityData.length > 0 && (
        <SensitivityHeatmap
          data={panel.sensitivityData}
          rowLabel={panel.sensitivityRowLabel}
          colLabel={panel.sensitivityColLabel}
          rowValues={panel.sensitivityRowValues}
          colValues={panel.sensitivityColValues}
        />
      )}
    </div>
  );
}
