"use client";

import type { MetricItem } from "@/types/analysis";
import { MetricCard } from "./MetricCard";

interface MetricCardGridProps {
  metrics: MetricItem[];
}

export function MetricCardGrid({ metrics }: MetricCardGridProps) {
  if (metrics.length === 0) return null;

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric, index) => (
        <MetricCard key={`${metric.label}-${index}`} metric={metric} />
      ))}
    </div>
  );
}
