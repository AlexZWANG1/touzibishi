"use client";

import type { DCFAssumption } from "@/types/analysis";

interface AssumptionListProps {
  assumptions: DCFAssumption[];
}

export function AssumptionList({ assumptions }: AssumptionListProps) {
  if (assumptions.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">核心假设</h3>
      </div>
      <div className="divide-y divide-[var(--iris-border)]">
        {assumptions.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between px-4 py-2.5 hover:bg-[var(--iris-surface-hover)]"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--iris-text-secondary)]">
                {item.label}
              </span>
              {item.sensitivity && (
                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
                  敏感
                </span>
              )}
            </div>
            <span className="font-mono text-sm font-medium text-[var(--iris-text)]">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
