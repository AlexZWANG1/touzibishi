"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { SearchBar } from "@/components/SearchBar";
import { WatchlistGrid } from "@/components/WatchlistGrid";
import type { WatchlistItem, HistoryItem } from "@/types/analysis";
import { getWatchlist, getHistory, startAnalysis } from "@/utils/api";

const QUICK_EXAMPLES = [
  { ticker: "AAPL", label: "Apple" },
  { ticker: "NVDA", label: "Nvidia" },
  { ticker: "MSFT", label: "Microsoft" },
  { ticker: "GOOGL", label: "Alphabet" },
  { ticker: "TSLA", label: "Tesla" },
];

const STATUS_COLORS: Record<string, string> = {
  complete: "#22C55E",
  running: "#3B82F6",
  error: "#EF4444",
  pending: "#A3A3A3",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })
    + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function HomePage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [wlLoading, setWlLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quickLoading, setQuickLoading] = useState<string | null>(null);
  const router = useRouter();

  const handleQuickStart = useCallback(async (ticker: string) => {
    if (quickLoading) return;
    setQuickLoading(ticker);
    try {
      const res = await startAnalysis({ query: ticker });
      router.push(`/analysis/${res.analysisId}`);
    } catch {
      setQuickLoading(null);
    }
  }, [quickLoading, router]);

  useEffect(() => {
    async function load() {
      try {
        const [wlRes, histRes] = await Promise.allSettled([
          getWatchlist(),
          getHistory(),
        ]);

        if (wlRes.status === "fulfilled") {
          setWatchlist(wlRes.value);
        }
        if (histRes.status === "fulfilled") {
          setHistory(histRes.value.items);
        }

        if (wlRes.status === "rejected" && histRes.status === "rejected") {
          setError("无法加载数据");
        }
      } catch {
        setError("无法加载数据");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleRefresh = useCallback(async () => {
    setWlLoading(true);
    try {
      const wl = await getWatchlist();
      setWatchlist(wl);
    } catch (err) {
      console.error("Failed to refresh watchlist:", err);
      setError("刷新失败，请重试");
    } finally {
      setWlLoading(false);
    }
  }, []);

  const isEmpty = watchlist.length === 0 && history.length === 0;

  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--iris-bg)" }}>
      {/* Search bar */}
      <div className="mx-auto max-w-5xl px-3 pt-2 pb-1">
        <SearchBar />
      </div>

      <div className="mx-auto max-w-5xl px-3 pb-4">
        {loading ? (
          <div className="flex items-center gap-1.5 py-3 font-mono text-[11px]" style={{ color: "var(--iris-text-muted)" }}>
            <div
              className="h-2.5 w-2.5 animate-spin border border-t-transparent"
              style={{ borderColor: "var(--iris-accent)", borderTopColor: "transparent" }}
            />
            LOADING...
          </div>
        ) : error ? (
          <div
            className="mt-1 border px-2 py-1.5 font-mono text-[11px]"
            style={{
              borderColor: "rgba(239, 68, 68, 0.3)",
              backgroundColor: "rgba(239, 68, 68, 0.05)",
              color: "#f87171",
            }}
          >
            {error}
          </div>
        ) : isEmpty ? (
          <div className="mt-2">
            {/* How it works */}
            <div
              className="border px-3 py-3"
              style={{
                borderColor: "var(--iris-border)",
                backgroundColor: "var(--iris-surface)",
              }}
            >
              <h2
                className="font-mono text-[10px] font-semibold uppercase tracking-[0.15em] mb-2"
                style={{ color: "var(--iris-text-muted)" }}
              >
                HOW IT WORKS
              </h2>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { step: "1", title: "输入标的", desc: "输入 ticker（如 AAPL）或公司名称" },
                  { step: "2", title: "AI 深度研究", desc: "自动拉取财报、构建 DCF、对比同业" },
                  { step: "3", title: "获取结论", desc: "估值结果、敏感性分析、投资建议" },
                ].map((item) => (
                  <div key={item.step} className="flex gap-2">
                    <span
                      className="flex-shrink-0 flex items-center justify-center h-4 w-4 font-mono text-[11px] font-bold"
                      style={{
                        backgroundColor: "rgba(245,128,37,0.12)",
                        color: "var(--iris-accent)",
                      }}
                    >
                      {item.step}
                    </span>
                    <div>
                      <div className="font-mono text-[11px] font-medium" style={{ color: "var(--iris-text)" }}>
                        {item.title}
                      </div>
                      <div className="text-[11px] mt-0.5" style={{ color: "var(--iris-text-muted)" }}>
                        {item.desc}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick start */}
            <div className="mt-3">
              <h3
                className="font-mono text-[10px] font-semibold uppercase tracking-[0.15em] mb-1.5 px-0.5"
                style={{ color: "var(--iris-text-muted)" }}
              >
                QUICK START
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_EXAMPLES.map((ex) => (
                  <button
                    key={ex.ticker}
                    onClick={() => handleQuickStart(ex.ticker)}
                    disabled={quickLoading !== null}
                    className="border px-2 py-1 font-mono text-[11px] transition-colors hover:border-[var(--iris-accent)] disabled:opacity-40"
                    style={{
                      borderColor: quickLoading === ex.ticker ? "var(--iris-accent)" : "var(--iris-border)",
                      backgroundColor: "var(--iris-surface)",
                      color: "var(--iris-text)",
                    }}
                  >
                    {quickLoading === ex.ticker ? (
                      <span className="flex items-center gap-1">
                        <span
                          className="inline-block h-2 w-2 animate-spin border border-t-transparent"
                          style={{ borderColor: "var(--iris-accent)", borderTopColor: "transparent" }}
                        />
                        {ex.ticker}
                      </span>
                    ) : (
                      <span>
                        <span className="font-bold" style={{ color: "var(--iris-accent)" }}>{ex.ticker}</span>
                        <span className="ml-1" style={{ color: "var(--iris-text-muted)" }}>{ex.label}</span>
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Watchlist */}
            {watchlist.length > 0 && (
              <WatchlistGrid items={watchlist} loading={wlLoading} onRefresh={handleRefresh} />
            )}

            {/* History */}
            {history.length > 0 && (
              <div className="mt-3">
                <div
                  className="flex items-center gap-2 px-1 py-1"
                  style={{ borderBottom: "1px solid var(--iris-accent)" }}
                >
                  <h2
                    className="font-mono text-[11px] font-semibold tracking-[0.15em] uppercase"
                    style={{ color: "var(--iris-text-muted)" }}
                  >
                    HISTORY
                  </h2>
                  <span className="font-mono text-[11px]" style={{ color: "var(--iris-accent)" }}>
                    {history.length}
                  </span>
                </div>

                <table className="mt-0.5 w-full" style={{ borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--iris-border)" }}>
                      <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>DATE</th>
                      <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>QUERY</th>
                      <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>TICKER</th>
                      <th className="text-left font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>STATUS</th>
                      <th className="text-right font-mono text-[10px] uppercase tracking-wider py-1 px-1 font-normal" style={{ color: "var(--iris-text-muted)" }}>TOKENS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item) => (
                      <tr
                        key={item.id}
                        className="cursor-pointer transition-colors"
                        style={{ borderBottom: "1px solid var(--iris-border)" }}
                        onClick={() => {
                          router.push(`/analysis/${item.id}`);
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--iris-surface)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                      >
                        <td className="font-mono text-[11px] py-0.5 px-1" style={{ color: "var(--iris-text-muted)" }}>
                          {formatDate(item.created_at)}
                        </td>
                        <td className="font-mono text-[11px] py-0.5 px-1 max-w-[260px] truncate" style={{ color: "var(--iris-text)" }}>
                          {item.query}
                        </td>
                        <td className="font-mono text-[11px] py-0.5 px-1 font-bold" style={{ color: "var(--iris-accent)" }}>
                          {item.ticker ?? "—"}
                        </td>
                        <td className="py-0.5 px-1">
                          <span
                            className="inline-block font-mono text-[11px] px-1 py-px font-medium uppercase"
                            style={{
                              color: STATUS_COLORS[item.status] || "#A3A3A3",
                              backgroundColor: `${STATUS_COLORS[item.status] || "#A3A3A3"}15`,
                            }}
                          >
                            {item.status}
                          </span>
                        </td>
                        <td className="font-mono text-right text-[11px] py-0.5 px-1" style={{ color: "var(--iris-text-muted)" }}>
                          {(item.tokens_in + item.tokens_out).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
