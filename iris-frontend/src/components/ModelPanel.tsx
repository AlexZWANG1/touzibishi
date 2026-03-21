"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { FairValueCard } from "./FairValueCard";
import { ImpliedMultiples } from "./ImpliedMultiples";
import { SensitivityHeatmap } from "./SensitivityHeatmap";
import { YearByYearTable } from "./YearByYearTable";

function LoadingSkeleton() {
  return (
    <div className="space-y-4 p-5 sm:p-6">
      <div className="prism-panel prism-shimmer h-[180px]" />
      <div className="prism-panel prism-shimmer h-[56px]" />
      <div className="prism-panel prism-shimmer h-[240px]" />
      <div className="prism-panel prism-shimmer h-[280px]" />
    </div>
  );
}

export function ModelPanel() {
  const panel = useAnalysisStore((s) => s.modelPanel);

  if (panel.loading) {
    return <LoadingSkeleton />;
  }

  if (!panel.fairValue && panel.yearByYear.length === 0 && panel.impliedMultiples.length === 0) {
    return <div className="px-6 py-8 text-[13px] text-[var(--t3)]">等待 DCF 与敏感性分析结果...</div>;
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      {panel.fairValue && <FairValueCard data={panel.fairValue} />}
      {panel.impliedMultiples.length > 0 && <ImpliedMultiples multiples={panel.impliedMultiples} />}
      {panel.yearByYear.length > 0 && <YearByYearTable data={panel.yearByYear} />}
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
