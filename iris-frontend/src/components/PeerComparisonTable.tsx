"use client";

import type { PeerCompany } from "@/types/analysis";
import { formatNumber } from "@/utils/formatters";

interface PeerComparisonTableProps {
  peers: PeerCompany[];
}

export function PeerComparisonTable({ peers }: PeerComparisonTableProps) {
  if (peers.length === 0) return null;

  const targetTicker = peers.find((peer) => peer.isTarget)?.ticker ?? peers[0]?.ticker;

  return (
    <div className="prism-panel overflow-hidden">
      <div className="border-b border-[var(--b1)] px-5 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--t1)]">Peer Comparison</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="border-b border-[var(--b1)] bg-[var(--bg-2)]">
              {["Ticker", "Market Cap", "P/E", "EV/EBITDA", "Revenue Growth", "Margin"].map((label) => (
                <th
                  key={label}
                  className="px-5 py-3 text-left font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {peers.map((peer) => {
              const target = peer.ticker === targetTicker;
              return (
                <tr
                  key={peer.ticker}
                  className="border-b border-[var(--b1)] last:border-b-0"
                  style={{ background: target ? "rgba(67,56,202,0.04)" : "transparent" }}
                >
                  <td className="px-5 py-4">
                    <div className="font-mono text-[13px] font-semibold text-[var(--ac)]">{peer.ticker}</div>
                    {peer.name && peer.name !== peer.ticker && (
                      <div className="mt-1 text-[12px] text-[var(--t3)]">{peer.name}</div>
                    )}
                  </td>
                  <td className="px-5 py-4 font-mono text-[13px] text-[var(--cy-t)]">
                    {peer.marketCap > 0 ? formatNumber(peer.marketCap) : "—"}
                  </td>
                  <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">
                    {peer.peRatio > 0 ? `${peer.peRatio.toFixed(1)}x` : "—"}
                  </td>
                  <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">
                    {peer.evEbitda > 0 ? `${peer.evEbitda.toFixed(1)}x` : "—"}
                  </td>
                  <td
                    className="px-5 py-4 font-mono text-[13px] font-semibold"
                    style={{ color: peer.revenueGrowth >= 0 ? "var(--green)" : "var(--red)" }}
                  >
                    {peer.revenueGrowth >= 0 ? "+" : ""}
                    {peer.revenueGrowth.toFixed(1)}%
                  </td>
                  <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">{peer.margin.toFixed(1)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
