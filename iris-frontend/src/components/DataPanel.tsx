"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { MetricCardGrid } from "./MetricCardGrid";
import { FinancialTable } from "./FinancialTable";

export function DataPanel() {
  const { metrics, financialTables, loading } = useAnalysisStore((s) => s.dataPanel);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--iris-accent)] border-t-transparent" />
          <p className="text-sm text-[var(--iris-text-muted)]">加载财务数据...</p>
        </div>
      </div>
    );
  }

  if (metrics.length === 0 && financialTables.length === 0) {
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
              d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          <p className="text-sm text-[var(--iris-text-muted)]">
            等待财务数据加载...
          </p>
          <p className="mt-1 text-xs text-[var(--iris-text-muted)]">
            IRIS 正在收集公司财务信息
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-5">
      {metrics.length > 0 && <MetricCardGrid metrics={metrics} />}
      {financialTables.map((table, idx) => (
        <FinancialTable key={idx} table={table} />
      ))}
    </div>
  );
}
