"use client";

import { useState, useEffect } from "react";
import { SearchBar } from "@/components/SearchBar";
import { WatchlistGrid } from "@/components/WatchlistGrid";
import type { WatchlistItem } from "@/types/analysis";
import { getWatchlist } from "@/utils/api";

export default function HomePage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getWatchlist();
        setWatchlist(data);
      } catch {
        setError("无法加载追踪列表");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-12 text-center">
        <h1 className="mb-3 text-4xl font-bold tracking-tight">
          IRIS
        </h1>
        <p className="text-lg text-[var(--iris-text-secondary)]">
          智能投资研究系统
        </p>
      </div>

      <SearchBar />

      <div className="mt-12">
        <h2 className="mb-6 text-xl font-semibold">追踪列表</h2>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--iris-accent)] border-t-transparent" />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-6 py-8 text-center text-red-400">
            {error}
          </div>
        ) : watchlist.length > 0 ? (
          <WatchlistGrid items={watchlist} />
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--iris-border)] px-6 py-16 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--iris-surface)]">
              <svg className="h-6 w-6 text-[var(--iris-text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
            <p className="text-[var(--iris-text-muted)]">
              还没有追踪任何公司。在上方输入 ticker 开始你的第一次分析。
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
