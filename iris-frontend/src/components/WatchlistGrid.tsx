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
    <div>
      {/* Section header */}
      <div
        className="flex items-center gap-2 px-1 py-1"
        style={{ borderBottom: "1px solid var(--iris-accent)" }}
      >
        <h2
          className="font-mono text-[11px] font-semibold tracking-[0.15em] uppercase"
          style={{ color: "var(--iris-text-muted)" }}
        >
          WATCHLIST
        </h2>
        <span
          className="font-mono text-[11px]"
          style={{ color: "var(--iris-accent)" }}
        >
          {items.length}
        </span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto font-mono text-[11px] px-1.5 py-px border cursor-pointer uppercase tracking-wider transition-colors"
          style={{
            borderColor: "var(--iris-border)",
            color: "var(--iris-text-muted)",
            backgroundColor: "transparent",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--iris-accent)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--iris-border)"; }}
        >
          {loading ? "..." : "REFRESH"}
        </button>
      </div>

      {loading && items.length === 0 ? (
        <div className="flex items-center gap-1.5 py-3 font-mono text-[11px]" style={{ color: "var(--iris-text-muted)" }}>
          <div
            className="h-2.5 w-2.5 animate-spin border border-t-transparent"
            style={{ borderColor: "var(--iris-accent)", borderTopColor: "transparent" }}
          />
          LOADING...
        </div>
      ) : (
        <table className="mt-0.5 w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--iris-border)" }}>
              <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>TICKER</th>
              <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>NAME</th>
              <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>PRICE</th>
              <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>GAP%</th>
              <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>FV</th>
              <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>REC</th>
              <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <WatchlistRow key={item.ticker} item={item} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
