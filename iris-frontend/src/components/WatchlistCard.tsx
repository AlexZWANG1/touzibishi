"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { WatchlistItem } from "@/types/analysis";
import { startAnalysis } from "@/utils/api";
import { formatCurrency } from "@/utils/formatters";

interface WatchlistRowProps {
  item: WatchlistItem;
}

const REC_META: Record<string, { label: string; bg: string; color: string }> = {
  BUY: { label: "买入", bg: "var(--green-bg)", color: "var(--green)" },
  STRONG_BUY: { label: "买入", bg: "var(--green-bg)", color: "var(--green)" },
  ACCUMULATE: { label: "买入", bg: "var(--green-bg)", color: "var(--green)" },
  HOLD: { label: "持有", bg: "var(--amber-bg)", color: "var(--amber)" },
  WATCH: { label: "观察", bg: "var(--amber-bg)", color: "var(--amber)" },
  REDUCE: { label: "减持", bg: "var(--red-bg)", color: "var(--red)" },
  TRIM: { label: "减持", bg: "var(--red-bg)", color: "var(--red)" },
  SELL: { label: "减持", bg: "var(--red-bg)", color: "var(--red)" },
  STRONG_SELL: { label: "减持", bg: "var(--red-bg)", color: "var(--red)" },
};

function recommendationMeta(value: string | null) {
  if (!value) {
    return { label: "观察", bg: "var(--bg-2)", color: "var(--t2)" };
  }
  return REC_META[value.toUpperCase().replace(/[\s-]+/g, "_")] || {
    label: value,
    bg: "var(--bg-2)",
    color: "var(--t2)",
  };
}

export function WatchlistRow({ item }: WatchlistRowProps) {
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  const [reflecting, setReflecting] = useState(false);

  const fairValid = item.fair_value != null && item.fair_value > 0 && !Number.isNaN(item.fair_value);
  const gapPct = fairValid && item.gap != null ? item.gap * 100 : null;
  const recommendation = recommendationMeta(item.recommendation);

  async function openAnalysis() {
    if (opening || reflecting) return;
    if (item.latest_run_id) {
      router.push(`/analysis/${item.latest_run_id}`);
      return;
    }

    setOpening(true);
    try {
      const res = await startAnalysis({
        query: `深度分析 ${item.ticker}，更新当前公允价值与交易判断`,
      });
      router.push(`/analysis/${res.analysisId}`);
    } catch (error) {
      console.error("Failed to open analysis from watchlist:", error);
      setOpening(false);
    }
  }

  return (
    <tr
      className="cursor-pointer border-b border-[var(--b1)] transition-colors hover:bg-[var(--bg-hover)]"
      onClick={() => void openAnalysis()}
    >
      <td className="px-5 py-4 font-mono text-[13px] font-semibold text-[var(--ac)]">{item.ticker}</td>
      <td className="max-w-[240px] px-5 py-4">
        <div className="truncate text-[14px] font-medium text-[var(--t1)]">{item.name ?? item.ticker}</div>
        {item.thesis && <div className="mt-1 truncate text-[12px] text-[var(--t3)]">{item.thesis}</div>}
      </td>
      <td className="px-5 py-4 text-right font-mono text-[13px] text-[var(--cy-t)]">
        {item.market_price != null ? formatCurrency(item.market_price) : "—"}
      </td>
      <td
        className="px-5 py-4 text-right font-mono text-[13px] font-semibold"
        style={{
          color:
            gapPct == null
              ? "var(--t3)"
              : gapPct >= 0
                ? "var(--green)"
                : "var(--red)",
        }}
      >
        {gapPct == null ? "—" : `${gapPct >= 0 ? "+" : ""}${gapPct.toFixed(1)}%`}
      </td>
      <td className="px-5 py-4 text-right font-mono text-[13px] text-[var(--cy-t)]">
        {fairValid ? formatCurrency(item.fair_value!) : "N/A"}
      </td>
      <td className="px-5 py-4 text-right">
        <span
          className="inline-flex rounded-pill px-3 py-1 text-[11px] font-semibold"
          style={{
            background: recommendation.bg,
            color: recommendation.color,
          }}
        >
          {recommendation.label}
        </span>
      </td>
      <td className="px-5 py-4 text-right">
        <button
          onClick={async (event) => {
            event.stopPropagation();
            if (reflecting || opening) return;
            setReflecting(true);
            try {
              const res = await startAnalysis({
                query: `复盘 ${item.ticker} 的最新财报表现与原始判断偏差`,
                mode: "learning",
              });
              router.push(`/analysis/${res.analysisId}`);
            } catch (error) {
              console.error("Failed to start reflection:", error);
              setReflecting(false);
            }
          }}
          disabled={reflecting || opening}
          className="rounded-md border border-[var(--ac-s)] bg-[var(--ac-s)] px-3 py-1.5 text-[11px] font-medium text-[var(--ac)] transition-colors hover:bg-[var(--ac-m)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {reflecting ? "处理中..." : opening ? "打开中..." : "复盘"}
        </button>
      </td>
    </tr>
  );
}
