"use client";

import type { MetricItem } from "@/types/analysis";
import { MetricCard } from "./MetricCard";

interface MetricCardGridProps {
  metrics: MetricItem[];
}

export function MetricCardGrid({ metrics }: MetricCardGridProps) {
  if (metrics.length === 0) return null;

  return (
    <div className="grid grid-cols-3 gap-[3px] mb-[10px]">
      {metrics.map((metric, idx) => (
        <MetricCard key={idx} metric={metric} />
      ))}
    </div>
  );
}
