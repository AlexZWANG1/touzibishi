"use client";

import type { MetricItem } from "@/types/analysis";

interface MetricCardProps {
  metric: MetricItem;
}

export function MetricCard({ metric }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] p-4">
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
        {metric.label}
      </p>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-xl font-semibold text-[var(--iris-text)]">
          {metric.value}
        </span>
        {metric.unit && (
          <span className="text-xs text-[var(--iris-text-muted)]">{metric.unit}</span>
        )}
      </div>
      {metric.change != null && (
        <div className="mt-1.5 flex items-center gap-1">
          <span
            className={`text-xs font-medium ${
              metric.change > 0
                ? "text-[var(--status-bullish)]"
                : metric.change < 0
                ? "text-[var(--status-bearish)]"
                : "text-[var(--iris-text-muted)]"
            }`}
          >
            {metric.change > 0 ? "+" : ""}
            {metric.change.toFixed(1)}%
          </span>
          {metric.changeLabel && (
            <span className="text-xs text-[var(--iris-text-muted)]">
              {metric.changeLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
