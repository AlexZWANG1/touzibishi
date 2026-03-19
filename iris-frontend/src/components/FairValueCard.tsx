"use client";

import type { FairValueData } from "@/types/analysis";
import { formatCurrency } from "@/utils/formatters";

interface FairValueCardProps {
  data: FairValueData;
}

const confidenceLabels: Record<string, string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

export function FairValueCard({ data }: FairValueCardProps) {
  const isUpside = data.upside >= 0;
  const isInvalid = data.fairValue <= 0 || isNaN(data.fairValue);

  // Calculate position percentages for the visual bar
  const maxVal = Math.max(Math.abs(data.fairValue), data.currentPrice) * 1.2 || 1;
  const fairPct = isInvalid ? 5 : Math.min(95, Math.max(5, (data.fairValue / maxVal) * 100));
  const currentPct = Math.min(
    95,
    Math.max(5, (data.currentPrice / maxVal) * 100)
  );

  return (
    <div className="border border-[var(--iris-border)] p-[10px] bg-[var(--iris-bg)]">
      {/* Row 1: Fair value + current price + gap */}
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-[10px] text-[var(--iris-text-muted)] uppercase tracking-[0.06em]">
          DCF FAIR VALUE
        </span>
        <span className={`font-mono text-[20px] font-bold ${isInvalid ? "text-[var(--iris-text-muted)]" : "text-[var(--iris-accent)]"}`}>
          {isInvalid ? "N/A" : formatCurrency(data.fairValue, data.currency)}
        </span>
        <span className="font-mono text-[11px] text-[var(--iris-text-muted)]">vs</span>
        <span className="font-mono text-[14px] text-[var(--iris-text-secondary)]">
          {formatCurrency(data.currentPrice, data.currency)}
        </span>
        <span
          className={`font-mono text-[15px] font-bold ${
            isUpside
              ? "text-[#22C55E]"
              : "text-[#EF4444]"
          }`}
        >
          {isUpside ? "+" : ""}
          {data.upside.toFixed(1)}%
        </span>
        <span className="font-mono text-[10px] text-[var(--iris-text-muted)]">
          {confidenceLabels[data.confidence] || "MED"} conf
        </span>
      </div>

      {/* Row 2: Progress bar with markers */}
      <div className="relative mt-3" style={{ height: 14 }}>
        {/* Track */}
        <div
          className="absolute bg-[var(--iris-border)]"
          style={{ left: 0, right: 0, top: 5, height: 4 }}
        >
          <div
            className="absolute left-0 top-0 h-full"
            style={{
              width: `${Math.min(fairPct, currentPct)}%`,
              backgroundColor: isUpside
                ? "rgba(34,197,94,0.35)"
                : "rgba(239,68,68,0.35)",
            }}
          />
        </div>

        {/* Fair value marker */}
        <div
          className="absolute"
          style={{ left: `${fairPct}%`, top: 0, transform: "translateX(-50%)" }}
        >
          <div style={{ width: 2, height: 14, background: "var(--iris-accent)" }} />
        </div>

        {/* Current price marker */}
        <div
          className="absolute"
          style={{ left: `${currentPct}%`, top: 0, transform: "translateX(-50%)" }}
        >
          <div style={{ width: 2, height: 14, background: "var(--iris-text-secondary)" }} />
        </div>
      </div>

      {/* Row 3: Bar labels */}
      <div className="mt-1 flex justify-between font-mono text-[9px] text-[var(--iris-text-muted)]">
        <span>0</span>
        <div className="flex gap-3">
          <span className="text-[var(--iris-text-secondary)]">
            Cur {formatCurrency(data.currentPrice, data.currency)}
          </span>
          <span className="text-[var(--iris-accent)]">
            FV {formatCurrency(data.fairValue, data.currency)}
          </span>
        </div>
      </div>
    </div>
  );
}
