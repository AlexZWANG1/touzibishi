"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { MetricCardGrid } from "./MetricCardGrid";
import { FinancialTable } from "./FinancialTable";

function LoadingSkeleton() {
  return (
    <div className="space-y-[3px] p-[6px]">
      <div className="grid grid-cols-3 gap-[3px]">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-12 bg-[var(--iris-surface)]" />
        ))}
      </div>
      <div className="h-48 bg-[var(--iris-surface)]" />
      <div className="h-36 bg-[var(--iris-surface)]" />
    </div>
  );
}

export function DataPanel() {
  const { metrics, financialTables, loading } = useAnalysisStore(
    (s) => s.dataPanel
  );

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (metrics.length === 0 && financialTables.length === 0) {
    return (
      <div className="px-[8px] py-[10px]">
        <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
          等待数据...
        </p>
      </div>
    );
  }

  return (
    <div className="p-[6px] space-y-[6px]">
      {metrics.length > 0 && <MetricCardGrid metrics={metrics} />}
      {financialTables.map((table, idx) => (
        <FinancialTable key={idx} table={table} />
      ))}
    </div>
  );
}
