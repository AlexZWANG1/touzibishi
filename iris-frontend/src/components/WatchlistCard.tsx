"use client";

import { useState } from "react";
import type { WatchlistItem } from "@/types/analysis";
import { startAnalysis } from "@/utils/api";
import { formatCurrency } from "@/utils/formatters";

interface WatchlistRowProps {
  item: WatchlistItem;
}

export function WatchlistRow({ item }: WatchlistRowProps) {
  const [reflecting, setReflecting] = useState(false);
  const fairValid = item.fair_value != null && item.fair_value > 0 && !isNaN(item.fair_value);
  const gapPct = fairValid && item.gap != null ? item.gap * 100 : null;
  const isPositiveGap = gapPct != null && gapPct > 0;
  const isNegativeGap = gapPct != null && gapPct < 0;

  return (
    <tr
      className="cursor-pointer transition-colors"
      style={{ borderBottom: "1px solid var(--iris-border)" }}
      onClick={() => {
        if (item.latest_run_id) {
          window.location.href = `/analysis/${item.latest_run_id}`;
        } else {
          window.location.href = `/analysis?query=${encodeURIComponent(item.ticker)}`;
        }
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "var(--iris-surface)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
    >
      {/* Ticker */}
      <td className="font-mono text-[12px] font-bold py-0.5 px-1" style={{ color: "var(--iris-accent)" }}>
        {item.ticker}
      </td>

      {/* Company name */}
      <td
        className="font-mono max-w-[180px] truncate text-[11px] py-0.5 px-1"
        style={{ color: "var(--iris-text-muted)" }}
      >
        {item.name ?? "—"}
      </td>

      {/* Market Price */}
      <td className="font-mono text-right text-[11px] py-0.5 px-1" style={{ color: "var(--iris-data)" }}>
        {item.market_price != null ? formatCurrency(item.market_price) : "—"}
      </td>

      {/* Gap % */}
      <td
        className="font-mono text-right text-[11px] font-bold py-0.5 px-1"
        style={{
          color: isPositiveGap
            ? "#22C55E"
            : isNegativeGap
            ? "#EF4444"
            : "var(--iris-text-secondary)",
        }}
      >
        {gapPct != null ? `${gapPct >= 0 ? "+" : ""}${gapPct.toFixed(1)}%` : "—"}
      </td>

      {/* Fair Value */}
      <td className="font-mono text-right text-[11px] py-0.5 px-1" style={{ color: fairValid ? "var(--iris-data)" : "var(--iris-text-muted)" }}>
        {fairValid ? formatCurrency(item.fair_value!) : "N/A"}
      </td>

      {/* Recommendation */}
      <td className="font-mono text-right text-[11px] uppercase py-0.5 px-1" style={{ color: "var(--iris-text-secondary)" }}>
        {item.recommendation ?? "—"}
      </td>

      {/* Actions */}
      <td className="text-right py-0.5 px-1">
        <button
          onClick={async (e) => {
            e.stopPropagation();
            if (reflecting) return;
            setReflecting(true);
            try {
              const res = await startAnalysis({
                query: `复盘 ${item.ticker} 的最新财报表现`,
                mode: 'learning',
              });
              window.location.href = `/analysis/${res.analysisId}`;
            } catch (err) {
              console.error('Failed to start reflection:', err);
              setReflecting(false);
            }
          }}
          className="font-mono px-1 py-px text-[11px] border transition-colors uppercase tracking-wider"
          style={{
            color: "var(--iris-accent)",
            borderColor: "var(--iris-border)",
            backgroundColor: "transparent",
            opacity: reflecting ? 0.4 : 0.7,
          }}
          onMouseEnter={(e) => {
            if (!reflecting) {
              (e.target as HTMLElement).style.opacity = "1";
              (e.target as HTMLElement).style.borderColor = "var(--iris-accent)";
            }
          }}
          onMouseLeave={(e) => {
            if (!reflecting) {
              (e.target as HTMLElement).style.opacity = "0.7";
              (e.target as HTMLElement).style.borderColor = "var(--iris-border)";
            }
          }}
          title="验证预测"
          disabled={reflecting}
        >
          {reflecting ? "..." : "复盘"}
        </button>
      </td>
    </tr>
  );
}
