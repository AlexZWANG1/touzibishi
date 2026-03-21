"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { MetricCardGrid } from "./MetricCardGrid";
import { FinancialTable } from "./FinancialTable";

function LoadingSkeleton() {
  return (
    <div className="space-y-4 p-5 sm:p-6">
      <div className="grid gap-3 md:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="prism-panel prism-shimmer h-[110px]" />
        ))}
      </div>
      <div className="prism-panel prism-shimmer h-[260px]" />
    </div>
  );
}

export function DataPanel() {
  const { metrics, financialTables, loading } = useAnalysisStore((s) => s.dataPanel);

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (metrics.length === 0 && financialTables.length === 0) {
    return <div className="px-6 py-8 text-[13px] text-[var(--t3)]">等待财务数据和市场指标...</div>;
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      {metrics.length > 0 && <MetricCardGrid metrics={metrics} />}
      {financialTables.map((table, index) => (
        <FinancialTable key={`${table.title}-${index}`} table={table} />
      ))}
    </div>
  );
}
