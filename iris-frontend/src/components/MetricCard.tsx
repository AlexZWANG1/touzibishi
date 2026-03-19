"use client";

import type { MetricItem } from "@/types/analysis";

interface MetricCardProps {
  metric: MetricItem;
}

export function MetricCard({ metric }: MetricCardProps) {
  const isPositive = metric.change != null && metric.change > 0;
  const isNegative = metric.change != null && metric.change < 0;

  return (
    <div className="p-[6px_8px] border border-[var(--iris-border)] bg-[var(--iris-bg)]">
      <p className="font-mono text-[9px] text-[var(--iris-text-muted)] uppercase tracking-[0.06em]">
        {metric.label}
      </p>

      <div className="mt-0.5 flex items-baseline gap-1">
        <span className="font-mono text-[15px] font-semibold text-[var(--iris-data)]">
          {metric.value}
        </span>
        {metric.unit && (
          <span className="font-mono text-[9px] text-[var(--iris-text-muted)]">
            {metric.unit}
          </span>
        )}
      </div>

      {metric.change != null && (
        <div className="mt-[1px] flex items-baseline gap-1">
          <span
            className={`font-mono text-[10px] ${
              isPositive
                ? "text-[#22C55E]"
                : isNegative
                  ? "text-[#EF4444]"
                  : "text-[var(--iris-text-muted)]"
            }`}
          >
            {isPositive ? "+" : ""}
            {metric.change.toFixed(1)}%
          </span>

          {metric.changeLabel && (
            <span className="font-mono text-[9px] text-[var(--iris-text-muted)]">
              {metric.changeLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
