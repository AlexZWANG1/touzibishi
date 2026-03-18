"use client";

import type { PeerCompany } from "@/types/analysis";
import { formatNumber } from "@/utils/formatters";

interface PeerComparisonTableProps {
  peers: PeerCompany[];
}

export function PeerComparisonTable({ peers }: PeerComparisonTableProps) {
  if (peers.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">同行对比</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
              <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                公司
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                市值
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                P/E
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                EV/EBITDA
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                营收增速
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                利润率
              </th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer) => (
              <tr
                key={peer.ticker}
                className="border-b border-[var(--iris-border)] last:border-0 hover:bg-[var(--iris-surface-hover)]"
              >
                <td className="px-4 py-2">
                  <div>
                    <span className="font-medium text-[var(--iris-text)]">
                      {peer.ticker}
                    </span>
                    <p className="text-xs text-[var(--iris-text-muted)]">{peer.name}</p>
                  </div>
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {formatNumber(peer.marketCap)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {peer.peRatio.toFixed(1)}x
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {peer.evEbitda.toFixed(1)}x
                </td>
                <td
                  className={`px-3 py-2 text-right font-mono ${
                    peer.revenueGrowth >= 0
                      ? "text-[var(--status-bullish)]"
                      : "text-[var(--status-bearish)]"
                  }`}
                >
                  {peer.revenueGrowth >= 0 ? "+" : ""}
                  {peer.revenueGrowth.toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {peer.margin.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
