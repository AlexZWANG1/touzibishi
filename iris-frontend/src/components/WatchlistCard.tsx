"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { WatchlistItem } from "@/types/analysis";
import { startAnalysis } from "@/utils/api";
import { formatCurrency } from "@/utils/formatters";

interface WatchlistRowProps {
  item: WatchlistItem;
}

export function WatchlistRow({ item }: WatchlistRowProps) {
  const router = useRouter();
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
          router.push(`/analysis/${item.latest_run_id}`);
        } else {
          router.push(`/analysis?query=${encodeURIComponent(item.ticker)}`);
        }
      }}
      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--iris-surface)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
    >
      {/* Ticker */}
      <td className="font-mono text-[12px] font-bold py-1.5 px-2" style={{ color: "var(--iris-accent)" }}>
        {item.ticker}
      </td>

      {/* Company name */}
      <td
        className="font-mono max-w-[180px] truncate text-[12px] py-1.5 px-2"
        style={{ color: "var(--iris-text-muted)" }}
      >
        {item.name ?? "—"}
      </td>

      {/* Market Price */}
      <td className="font-mono text-right text-[12px] py-1.5 px-2" style={{ color: "var(--iris-data)" }}>
        {item.market_price != null ? formatCurrency(item.market_price) : "—"}
      </td>

      {/* Gap % */}
      <td
        className="font-mono text-right text-[12px] font-bold py-1.5 px-2"
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
      <td className="font-mono text-right text-[12px] py-1.5 px-2" style={{ color: fairValid ? "var(--iris-data)" : "var(--iris-text-muted)" }}>
        {fairValid ? formatCurrency(item.fair_value!) : "N/A"}
      </td>

      {/* Recommendation */}
      <td className="font-mono text-right text-[12px] uppercase py-1.5 px-2" style={{ color: "var(--iris-text-secondary)" }}>
        {item.recommendation ?? "—"}
      </td>

      {/* Actions */}
      <td className="text-right py-1.5 px-2">
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
              router.push(`/analysis/${res.analysisId}`);
            } catch (err) {
              console.error('Failed to start reflection:', err);
              setReflecting(false);
            }
          }}
          className="font-mono px-1 py-px text-[12px] border transition-colors uppercase tracking-wider hover:opacity-100 hover:border-[var(--iris-accent)] disabled:opacity-40"
          style={{
            color: "var(--iris-accent)",
            borderColor: "var(--iris-border)",
            backgroundColor: "transparent",
            opacity: reflecting ? 0.4 : 0.7,
          }}
          title="Verify prediction / 验证预测"
          disabled={reflecting}
        >
          {reflecting ? "..." : "复盘"}
        </button>
      </td>
    </tr>
  );
}
