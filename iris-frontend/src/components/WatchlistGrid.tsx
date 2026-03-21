"use client";

import type { WatchlistItem } from "@/types/analysis";
import { WatchlistRow } from "./WatchlistCard";

interface WatchlistGridProps {
  items: WatchlistItem[];
  loading: boolean;
  onRefresh: () => void;
}

export function WatchlistGrid({ items, loading, onRefresh }: WatchlistGridProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="font-display text-[28px] font-medium tracking-[-0.03em] text-[var(--ink)]">
          Watchlist
        </h2>
        <span className="prism-mono-chip">{items.length}</span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto rounded-md border border-[var(--b2)] bg-[var(--bg-w)] px-3 py-2 text-[12px] font-medium text-[var(--t2)] shadow-card transition-all hover:border-[var(--b3)] hover:text-[var(--t1)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="prism-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="border-b border-[var(--b2)] bg-[var(--bg-2)]">
                {["Ticker", "Name", "Price", "Gap", "Fair Value", "建议", "操作"].map((label, index) => (
                  <th
                    key={label}
                    className="px-5 py-3 text-left font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]"
                    style={{ textAlign: index >= 2 ? "right" : "left" }}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-[14px] text-[var(--t3)]">
                    暂无追踪标的，先在首页发起一轮分析。
                  </td>
                </tr>
              ) : (
                items.map((item) => <WatchlistRow key={item.ticker} item={item} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
