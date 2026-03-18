"use client";

import type { WatchlistItem } from "@/types/analysis";
import { WatchlistCard } from "./WatchlistCard";

interface WatchlistGridProps {
  items: WatchlistItem[];
}

export function WatchlistGrid({ items }: WatchlistGridProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <WatchlistCard key={item.ticker} item={item} />
      ))}
    </div>
  );
}
