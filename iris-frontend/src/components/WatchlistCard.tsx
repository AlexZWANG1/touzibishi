"use client";

import Link from "next/link";
import type { WatchlistItem } from "@/types/analysis";
import { formatCurrency } from "@/utils/formatters";

interface WatchlistCardProps {
  item: WatchlistItem;
}

export function WatchlistCard({ item }: WatchlistCardProps) {
  const gapPct = item.gap != null ? item.gap * 100 : null;

  return (
    <Link
      href={`/analysis?query=${encodeURIComponent(item.ticker)}`}
      className="group block rounded-xl border border-[var(--iris-border)] bg-[var(--iris-surface)] p-5 transition-all hover:border-[var(--iris-accent)]/40 hover:bg-[var(--iris-surface-hover)]"
    >
      <div className="mb-3 flex items-start justify-between">
        <h3 className="text-base font-semibold text-[var(--iris-text)] group-hover:text-[var(--iris-accent)]">
          {item.ticker}
        </h3>
        {item.alerts.length > 0 && (
          <span className="rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-medium text-red-400">
            {item.alerts.length} 告警
          </span>
        )}
      </div>

      <div className="space-y-2 text-sm">
        {item.market_price != null && (
          <div className="flex justify-between">
            <span className="text-[var(--iris-text-muted)]">现价</span>
            <span className="font-mono">{formatCurrency(item.market_price)}</span>
          </div>
        )}
        {item.fair_value != null && (
          <div className="flex justify-between">
            <span className="text-[var(--iris-text-muted)]">公允价值</span>
            <span className="font-mono">{formatCurrency(item.fair_value)}</span>
          </div>
        )}
        {gapPct != null && (
          <div className="flex justify-between">
            <span className="text-[var(--iris-text-muted)]">潜在空间</span>
            <span
              className={`font-mono ${
                gapPct > 0
                  ? "text-[var(--status-bullish)]"
                  : gapPct < 0
                  ? "text-[var(--status-bearish)]"
                  : "text-[var(--iris-text)]"
              }`}
            >
              {gapPct >= 0 ? "+" : ""}
              {gapPct.toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {item.thesis && (
        <div className="mt-3 border-t border-[var(--iris-border)] pt-3">
          <p className="line-clamp-2 text-xs text-[var(--iris-text-muted)]">
            {item.thesis}
          </p>
        </div>
      )}

      {item.alerts.length > 0 && (
        <div className="mt-2 space-y-1">
          {item.alerts.map((alert, i) => (
            <div
              key={i}
              className="rounded bg-red-500/5 px-2 py-1 text-xs text-red-400"
            >
              {alert.message}
            </div>
          ))}
        </div>
      )}
    </Link>
  );
}
