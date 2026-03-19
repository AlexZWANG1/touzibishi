"use client";

import type { PeerCompany } from "@/types/analysis";
import { formatNumber } from "@/utils/formatters";

interface PeerComparisonTableProps {
  peers: PeerCompany[];
}

export function PeerComparisonTable({ peers }: PeerComparisonTableProps) {
  if (peers.length === 0) return null;

  const targetTicker =
    peers.find((p) => (p as Record<string, unknown>).isTarget)?.ticker ??
    peers[0]?.ticker;

  // Compute median P/E and EV/EBITDA for premium/discount
  const validPE = peers.filter((p) => p.peRatio > 0).map((p) => p.peRatio).sort((a, b) => a - b);
  const validEV = peers.filter((p) => p.evEbitda > 0).map((p) => p.evEbitda).sort((a, b) => a - b);
  const medianPE = validPE.length > 0 ? validPE[Math.floor(validPE.length / 2)] : 0;
  const medianEV = validEV.length > 0 ? validEV[Math.floor(validEV.length / 2)] : 0;

  const thClass =
    "p-[3px_8px] font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)] bg-[var(--iris-surface)] border-b border-[var(--iris-border)]";

  return (
    <div className="border border-[var(--iris-border)] overflow-hidden">
      <div className="p-[5px_8px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <span className="font-mono text-[11px] text-[var(--iris-accent)] uppercase tracking-[0.08em]">
          Peer Comparison
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr>
              <th className={`${thClass} text-left`}>Ticker</th>
              <th className={`${thClass} text-right`}>Mkt Cap</th>
              <th className={`${thClass} text-right`}>P/E</th>
              <th className={`${thClass} text-right`}>EV/EBITDA</th>
              <th className={`${thClass} text-right`}>Rev Growth</th>
              <th className={`${thClass} text-right`}>Margin</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer, idx) => {
              const isTarget = peer.ticker === targetTicker;
              const isLast = idx === peers.length - 1;
              const pePrem = medianPE > 0 && peer.peRatio > 0 ? ((peer.peRatio / medianPE - 1) * 100) : null;
              const evPrem = medianEV > 0 && peer.evEbitda > 0 ? ((peer.evEbitda / medianEV - 1) * 100) : null;

              return (
                <tr
                  key={peer.ticker}
                  style={{
                    borderBottom: isLast ? "none" : "1px solid rgba(30,32,48,0.3)",
                    background: isTarget ? "rgba(245,128,37,0.06)" : undefined,
                  }}
                >
                  <td
                    className="p-[3px_8px] font-mono"
                    style={{
                      borderLeft: isTarget ? "2px solid var(--iris-accent)" : undefined,
                    }}
                  >
                    <span
                      className={`font-medium ${
                        isTarget
                          ? "text-[var(--iris-accent)]"
                          : "text-[var(--iris-text)]"
                      }`}
                    >
                      {peer.ticker}
                    </span>
                    {peer.name && peer.name !== peer.ticker && (
                      <span className="ml-1 text-[10px] text-[var(--iris-text-muted)]">
                        {peer.name}
                      </span>
                    )}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-data)]">
                    {peer.marketCap > 0 ? formatNumber(peer.marketCap) : "--"}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-data)]">
                    {peer.peRatio > 0 ? (
                      <span>
                        {peer.peRatio.toFixed(1)}x
                        {isTarget && pePrem !== null && (
                          <span className={`ml-1 text-[10px] ${pePrem >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                            {pePrem >= 0 ? "+" : ""}{pePrem.toFixed(0)}%
                          </span>
                        )}
                      </span>
                    ) : "--"}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-data)]">
                    {peer.evEbitda > 0 ? (
                      <span>
                        {peer.evEbitda.toFixed(1)}x
                        {isTarget && evPrem !== null && (
                          <span className={`ml-1 text-[10px] ${evPrem >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                            {evPrem >= 0 ? "+" : ""}{evPrem.toFixed(0)}%
                          </span>
                        )}
                      </span>
                    ) : "--"}
                  </td>
                  <td
                    className={`p-[3px_8px] text-right font-mono ${
                      peer.revenueGrowth >= 0
                        ? "text-[#22C55E]"
                        : "text-[#EF4444]"
                    }`}
                  >
                    {peer.revenueGrowth >= 0 ? "+" : ""}
                    {peer.revenueGrowth.toFixed(1)}%
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-data)]">
                    {peer.margin.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
