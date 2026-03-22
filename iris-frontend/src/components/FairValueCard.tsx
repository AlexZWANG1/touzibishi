"use client";

import type { FairValueData } from "@/types/analysis";
import { formatCurrency } from "@/utils/formatters";

interface FairValueCardProps {
  data: FairValueData;
}

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "高置信",
  medium: "中置信",
  low: "低置信",
};

export function FairValueCard({ data }: FairValueCardProps) {
  const upside = data.upside >= 0;
  const safeFairValue = data.fairValue > 0 && !Number.isNaN(data.fairValue);
  const maxValue = Math.max(Math.abs(data.fairValue), data.currentPrice) * 1.25 || 1;
  const fairPct = safeFairValue ? Math.min(92, Math.max(8, (data.fairValue / maxValue) * 100)) : 8;
  const currentPct = Math.min(92, Math.max(8, (data.currentPrice / maxValue) * 100));

  return (
    <div className="prism-panel p-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
          公允价值
        </div>
        <div className="font-mono text-[34px] font-semibold text-[var(--ac)]">
          {safeFairValue ? formatCurrency(data.fairValue, data.currency) : "N/A"}
        </div>
        <div className="text-[14px] text-[var(--t3)]">vs {formatCurrency(data.currentPrice, data.currency)}</div>
        <div
          className="font-mono text-[20px] font-semibold"
          style={{ color: upside ? "var(--green)" : "var(--red)" }}
        >
          {upside ? "+" : ""}
          {data.upside.toFixed(1)}%
        </div>
        <div className="rounded-pill bg-[var(--bg-2)] px-3 py-1 font-mono text-[10px] text-[var(--t3)]">
          {CONFIDENCE_LABELS[data.confidence] || "中置信"}
        </div>
      </div>

      <div className="mt-5">
        <div className="relative h-[8px] rounded-full bg-[var(--bg-2)]">
          <div
            className="absolute left-0 top-0 h-full rounded-full"
            style={{
              width: `${Math.max(fairPct, currentPct)}%`,
              background: upside ? "rgba(21,128,61,0.12)" : "rgba(185,28,28,0.12)",
            }}
          />
          <div
            className="absolute top-[-4px] h-[16px] w-[3px] rounded-full bg-[var(--t3)]"
            style={{ left: `calc(${currentPct}% - 1px)` }}
          />
          <div
            className="absolute top-[-4px] h-[16px] w-[3px] rounded-full bg-[var(--ac)]"
            style={{ left: `calc(${fairPct}% - 1px)` }}
          />
        </div>
        <div className="mt-2 flex justify-between font-mono text-[10px] text-[var(--t3)]">
          <span>$0</span>
          <span>
            现价 {formatCurrency(data.currentPrice, data.currency)} · 公允 {formatCurrency(data.fairValue, data.currency)}
          </span>
        </div>
      </div>
    </div>
  );
}
