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
        <h2 className="font-display text-fluid-h2 font-medium tracking-[-0.03em] text-[var(--ink)]">
          追踪列表
        </h2>
        <span className="prism-mono-chip">{items.length}</span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto rounded-md border border-[var(--b2)] bg-[var(--bg-w)] px-3 py-2 text-[12px] font-medium text-[var(--t2)] shadow-card transition-all hover:border-[var(--b3)] hover:text-[var(--t1)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "刷新中..." : "刷新"}
        </button>
      </div>

      <div className="prism-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="border-b border-[var(--b2)] bg-[var(--bg-2)]">
                {["代码", "名称", "现价", "偏离", "公允价值", "建议", "操作"].map((label, index) => (
                  <th
                    key={label}
                    className={`px-5 py-3 font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)] ${
                      index >= 2 ? "text-right" : "text-left"
                    }`}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center">
                    <p className="text-[14px] font-medium text-[var(--t1)]">追踪列表为空</p>
                    <p className="mx-auto mt-2 max-w-[320px] text-[12px] leading-[1.7] text-[var(--t3)]">
                      完成一轮深度分析后，Prism 会自动把带有估值结论的标的加入这里。你可以在此追踪价格变动和建议更新。
                    </p>
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
