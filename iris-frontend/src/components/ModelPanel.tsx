"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { FairValueCard } from "./FairValueCard";
import { ImpliedMultiples } from "./ImpliedMultiples";
import { SensitivityHeatmap } from "./SensitivityHeatmap";
import { YearByYearTable } from "./YearByYearTable";
import { WarningsBanner } from "./WarningsBanner";
import { CrossCheckBadge } from "./CrossCheckBadge";

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

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <div className="space-y-5 p-5 sm:p-6">
      {panel.fairValue && <FairValueCard data={panel.fairValue} />}
      {panel.crossCheck && <CrossCheckBadge data={panel.crossCheck} />}
      {panel.warnings.length > 0 && <WarningsBanner warnings={panel.warnings} />}
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
      {panel.excelPath && (
        <a
          href={`${API_BASE}/api/download-excel?path=${encodeURIComponent(panel.excelPath)}`}
          className="flex items-center gap-2 rounded-lg border border-[var(--b1)] bg-[var(--bg-2)] px-4 py-3 text-[13px] font-medium text-[var(--t1)] transition-colors hover:bg-[var(--bg-3)]"
          download
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download DCF Workbook (.xlsx)
        </a>
      )}
    </div>
  );
}
