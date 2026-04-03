"use client";

import type { CrossCheckResult } from "@/types/analysis";

interface CrossCheckBadgeProps {
  data: CrossCheckResult;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  aligned: { bg: "rgba(21,128,61,0.08)", text: "var(--green)", label: "DCF \u2248 Peers" },
  stretched: { bg: "rgba(185,28,28,0.08)", text: "var(--red)", label: "DCF > Peers" },
  conservative: { bg: "rgba(245,158,11,0.08)", text: "#B45309", label: "DCF < Peers" },
  insufficient_data: { bg: "var(--bg-2)", text: "var(--t3)", label: "Insufficient Data" },
};

export function CrossCheckBadge({ data }: CrossCheckBadgeProps) {
  const style = STATUS_STYLES[data.status] || STATUS_STYLES.insufficient_data;

  return (
    <div className="prism-panel p-4" style={{ background: style.bg }}>
      <div className="flex items-center gap-3">
        <span
          className="rounded-full px-3 py-1 text-[11px] font-semibold"
          style={{ color: style.text, background: style.bg }}
        >
          {style.label}
        </span>
        <span className="text-[12px] text-[var(--t2)]">{data.message}</span>
      </div>
      {data.implied_fwd_pe != null && data.peer_median_fwd_pe != null && (
        <div className="mt-2 flex gap-4 font-mono text-[11px] text-[var(--t3)]">
          <span>DCF Implied P/E: {data.implied_fwd_pe?.toFixed(1)}x</span>
          <span>Peer Median: {data.peer_median_fwd_pe?.toFixed(1)}x</span>
          <span>Premium: {((data.premium_vs_peers || 0) * 100).toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
}
