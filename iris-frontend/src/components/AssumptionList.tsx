"use client";

import type { DCFAssumption } from "@/types/analysis";

interface AssumptionListProps {
  assumptions: DCFAssumption[];
}

export function AssumptionList({ assumptions }: AssumptionListProps) {
  if (assumptions.length === 0) return null;

  return (
    <div className="border border-[var(--b1)] overflow-hidden">
      <div className="p-[5px_8px] border-b border-[var(--b1)] bg-[var(--bg-w)]">
        <span className="font-mono text-[11px] text-[var(--ac)] uppercase tracking-[0.08em]">
          核心假设
        </span>
      </div>
      <div>
        {assumptions.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between px-[8px] py-[3px] font-mono text-[11px]"
            style={{
              borderBottom: idx < assumptions.length - 1 ? "1px solid rgba(30,32,48,0.3)" : "none",
            }}
          >
            <span className="text-[var(--t2)]">
              {item.label}
              {item.sensitivity && (
                <span className="ml-1 text-[10px] text-[#F59E0B]">*</span>
              )}
            </span>
            <span className="font-mono font-semibold text-[var(--cy)]">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
