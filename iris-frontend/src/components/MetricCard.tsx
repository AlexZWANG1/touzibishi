"use client";

import type { MetricItem } from "@/types/analysis";

interface MetricCardProps {
  metric: MetricItem;
}

export function MetricCard({ metric }: MetricCardProps) {
  const positive = metric.change != null && metric.change > 0;
  const negative = metric.change != null && metric.change < 0;

  return (
    <div className="prism-panel p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
        {metric.label}
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-[26px] font-semibold text-[var(--cy-t)]">{metric.value}</span>
        {metric.unit && <span className="font-mono text-[11px] text-[var(--t3)]">{metric.unit}</span>}
      </div>
      {metric.change != null && (
        <div
          className="mt-3 font-mono text-[12px] font-medium"
          style={{
            color: positive ? "var(--green)" : negative ? "var(--red)" : "var(--t3)",
          }}
        >
          {positive ? "+" : ""}
          {metric.change.toFixed(1)}%
          {metric.changeLabel && <span className="ml-2 font-sans text-[12px] text-[var(--t3)]">{metric.changeLabel}</span>}
        </div>
      )}
    </div>
  );
}
