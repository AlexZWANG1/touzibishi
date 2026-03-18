"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { FairValueCard } from "./FairValueCard";
import { AssumptionList } from "./AssumptionList";
import { ImpliedMultiples } from "./ImpliedMultiples";
import { SensitivityHeatmap } from "./SensitivityHeatmap";
import { YearByYearTable } from "./YearByYearTable";

export function ModelPanel() {
  const panel = useAnalysisStore((s) => s.modelPanel);

  if (panel.loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--phase-evaluate)] border-t-transparent" />
          <p className="text-sm text-[var(--iris-text-muted)]">构建估值模型...</p>
        </div>
      </div>
    );
  }

  if (!panel.fairValue && panel.assumptions.length === 0) {
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
              d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          <p className="text-sm text-[var(--iris-text-muted)]">
            等待 DCF 模型构建...
          </p>
          <p className="mt-1 text-xs text-[var(--iris-text-muted)]">
            IRIS 将在收集足够数据后构建估值模型
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-5">
      {panel.fairValue && <FairValueCard data={panel.fairValue} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <AssumptionList assumptions={panel.assumptions} />
        <ImpliedMultiples multiples={panel.impliedMultiples} />
      </div>

      <SensitivityHeatmap
        data={panel.sensitivityData}
        rowLabel={panel.sensitivityRowLabel}
        colLabel={panel.sensitivityColLabel}
        rowValues={panel.sensitivityRowValues}
        colValues={panel.sensitivityColValues}
      />

      <YearByYearTable data={panel.yearByYear} />
    </div>
  );
}
