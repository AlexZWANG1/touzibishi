"use client";

import type { MetricItem } from "@/types/analysis";
import { MetricCard } from "./MetricCard";

interface MetricCardGridProps {
  metrics: MetricItem[];
}

export function MetricCardGrid({ metrics }: MetricCardGridProps) {
  if (metrics.length === 0) return null;

  const primary = metrics.slice(0, 3);
  const secondary = metrics.slice(3);

  return (
    <div className="space-y-3">
      {primary.length > 0 && (
        <div className="grid gap-3 md:grid-cols-3">
          {primary.map((m, i) => (
            <MetricCard key={`${m.label}-${i}`} metric={m} />
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <div className="prism-panel overflow-hidden">
          {secondary.map((m, i) => (
            <MetricCard key={`${m.label}-${i + 3}`} metric={m} size="compact" />
          ))}
        </div>
      )}
    </div>
  );
}
