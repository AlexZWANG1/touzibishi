"use client";

import type { FairValueData } from "@/types/analysis";
import { formatCurrency } from "@/utils/formatters";

interface FairValueCardProps {
  data: FairValueData;
}

const confidenceConfig = {
  high: { label: "高", color: "text-[var(--status-bullish)]", bg: "bg-green-500/10" },
  medium: { label: "中", color: "text-[var(--status-neutral)]", bg: "bg-amber-500/10" },
  low: { label: "低", color: "text-[var(--status-bearish)]", bg: "bg-red-500/10" },
};

export function FairValueCard({ data }: FairValueCardProps) {
  const conf = confidenceConfig[data.confidence];
  const isUpside = data.upside >= 0;

  return (
    <div className="rounded-xl border border-[var(--iris-border)] bg-[var(--iris-surface)] p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
            DCF 公允价值
          </p>
          <p className="font-mono text-3xl font-bold text-[var(--iris-text)]">
            {formatCurrency(data.fairValue, data.currency)}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${conf.color} ${conf.bg}`}>
          置信度: {conf.label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-[var(--iris-text-muted)]">当前股价</p>
          <p className="font-mono text-lg font-semibold text-[var(--iris-text-secondary)]">
            {formatCurrency(data.currentPrice, data.currency)}
          </p>
        </div>
        <div>
          <p className="text-xs text-[var(--iris-text-muted)]">潜在空间</p>
          <p
            className={`font-mono text-lg font-semibold ${
              isUpside ? "text-[var(--status-bullish)]" : "text-[var(--status-bearish)]"
            }`}
          >
            {isUpside ? "+" : ""}
            {data.upside.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Visual bar */}
      <div className="mt-4">
        <div className="relative h-2 overflow-hidden rounded-full bg-[var(--iris-border)]">
          <div
            className="absolute left-0 top-0 h-full rounded-full"
            style={{
              width: `${Math.min(
                100,
                Math.max(5, (data.currentPrice / data.fairValue) * 100)
              )}%`,
              background: isUpside ? "var(--status-bullish)" : "var(--status-bearish)",
            }}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-[var(--iris-text-muted)]">
          <span>$0</span>
          <span>公允价值</span>
        </div>
      </div>
    </div>
  );
}
