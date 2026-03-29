"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchBar, type AnalysisMode } from "@/components/SearchBar";
import { WatchlistGrid } from "@/components/WatchlistGrid";
import { PortfolioSummary, type Portfolio } from "@/components/PortfolioSummary";
import type { WatchlistItem, HistoryItem } from "@/types/analysis";
import { getHistory, getPortfolio, getWatchlist, startAnalysis } from "@/utils/api";
import { classNames } from "@/utils/formatters";

const CAPABILITY_MODULES = [
  {
    key: "fundamental",
    title: "基本面研究",
    description: "围绕核心假说建立证据链，自动搜索资讯并更新基本面判断。",
    chips: ["假说面板", "证据卡片", "资讯搜索"],
    bar: "linear-gradient(90deg, var(--sp2), var(--sp3))",
    iconStyle: { background: "var(--cy-s)", color: "var(--cy)" },
    iconPath: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    templates: [
      "深度分析 AAPL 最新财报，重点看服务业务增长与毛利率改善。",
      "分析 AI 芯片行业竞争格局，比较 NVDA、AMD 与博通的核心差异。",
    ],
  },
  {
    key: "valuation",
    title: "估值研究",
    description: "把财务数据、DCF 模型和可比公司压到一个清晰的估值框架里。",
    chips: ["财务数据", "DCF 模型", "可比公司"],
    bar: "linear-gradient(90deg, var(--sp1), var(--sp2))",
    iconStyle: { background: "var(--ac-s)", color: "var(--ac)" },
    iconPath: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z",
    templates: [
      "对比 MSFT 和 GOOGL 云业务估值，给出 multiples 与 DCF 双重结论。",
      "用 12% WACC 重新估值 TSLA，并输出敏感性热力图。",
    ],
  },
  {
    key: "trading",
    title: "交易策略建议",
    description: "把研究结论转成交易动作、仓位建议和校准反馈，形成闭环。",
    chips: ["策略面板", "信号跟踪", "校准数据"],
    bar: "linear-gradient(90deg, var(--sp4), var(--sp5))",
    iconStyle: { background: "var(--amber-bg)", color: "var(--amber)" },
    iconPath: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
    templates: [
      "为 META 生成交易策略建议，给出目标仓位、信号强度和约束检查。",
      "复盘 NVDA 最新财报预测，检查原假设和现实结果偏差。",
    ],
  },
];

const STATUS_META: Record<string, string> = {
  complete: "已完成",
  running: "进行中",
  error: "失败",
  pending: "等待中",
};

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  complete: { color: "var(--green)", bg: "var(--green-bg)" },
  running: { color: "var(--ac)", bg: "var(--ac-s)" },
  error: { color: "var(--red)", bg: "var(--red-bg)" },
  pending: { color: "var(--t2)", bg: "var(--bg-2)" },
};

function CapabilityIcon({
  path,
  style,
}: {
  path: string;
  style: { background: string; color: string };
}) {
  return (
    <span
      className="inline-flex h-9 w-9 items-center justify-center rounded-md"
      style={style}
      aria-hidden="true"
    >
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d={path} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} ${d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export default function HomePage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [wlLoading, setWlLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<AnalysisMode>("analysis");
  const [searchLoading, setSearchLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    async function load() {
      try {
        const [watchlistResult, portfolioResult, historyResult] = await Promise.allSettled([
          getWatchlist(),
          getPortfolio(),
          getHistory(),
        ]);

        if (watchlistResult.status === "fulfilled") {
          setWatchlist(watchlistResult.value);
        }

        if (portfolioResult.status === "fulfilled" && portfolioResult.value) {
          setPortfolio(portfolioResult.value as Portfolio);
        }

        if (historyResult.status === "fulfilled") {
          setHistory(historyResult.value.items);
        }

        if (watchlistResult.status === "rejected" && historyResult.status === "rejected") {
          setError("无法加载首页数据，请检查后端服务。");
        }
      } catch {
        setError("无法加载首页数据，请检查后端服务。");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  const handleRefresh = useCallback(async () => {
    setWlLoading(true);
    try {
      const [wlResult, pfResult] = await Promise.allSettled([
        getWatchlist(),
        getPortfolio(),
      ]);
      if (wlResult.status === "fulfilled") setWatchlist(wlResult.value);
      if (pfResult.status === "fulfilled" && pfResult.value) setPortfolio(pfResult.value as Portfolio);
    } catch (refreshError) {
      console.error("Failed to refresh:", refreshError);
      setError("刷新失败。");
    } finally {
      setWlLoading(false);
    }
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || searchLoading) return;

    setSearchLoading(true);
    try {
      const result = await startAnalysis({ query: trimmed, mode });
      router.push(`/analysis/${result.analysisId}`);
    } catch (submitError) {
      console.error("Failed to start analysis:", submitError);
      setSearchLoading(false);
      setError("无法启动分析，请稍后重试。");
    }
  }, [mode, query, router, searchLoading]);

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="mx-auto max-w-[980px] px-5 pb-20 pt-10 sm:px-8">
        <section className="animate-fade-up">
          <div className="prism-kicker">Prism Research Intelligence</div>
          <div className="mt-5 grid gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <h1 className="max-w-[700px] font-display text-fluid-hero leading-[1.04] tracking-[-0.04em] text-[var(--ink)]">
                Decompose complexity.
                <br />
                <em className="font-normal text-[var(--ac)]">See clearly.</em>
              </h1>
            </div>
            <p className="max-w-[420px] text-[15px] leading-[1.8] text-[var(--t2)]">
              一束复杂的市场数据进来，Prism 将它分解成清晰的光谱：基本面假说、估值模型、交易信号。
            </p>
          </div>
        </section>

        <section className="mt-9 animate-fade-up [animation-delay:120ms]">
          <SearchBar
            value={query}
            mode={mode}
            loading={searchLoading}
            onChange={setQuery}
            onModeChange={setMode}
            onSubmit={handleSubmit}
          />
        </section>

        <section className="gap-fluid-section animate-fade-up [animation-delay:240ms]">
          <div className="prism-panel overflow-hidden divide-y divide-[var(--b1)]">
            {CAPABILITY_MODULES.map((module) => (
              <details key={module.key} className="group">
                <summary className="flex cursor-pointer items-center gap-4 px-5 py-4 transition-colors hover:bg-[var(--bg-hover)] [&::-webkit-details-marker]:hidden list-none">
                  <div className="h-[3px] w-6 rounded-full" style={{ background: module.bar }} />
                  <CapabilityIcon path={module.iconPath} style={module.iconStyle} />
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[15px] font-semibold text-[var(--t1)]">{module.title}</h2>
                    <p className="mt-0.5 text-[12px] text-[var(--t3)]">{module.description}</p>
                  </div>
                  <span className="text-[var(--t4)] transition-transform group-open:rotate-90">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                </summary>
                <div className="border-t border-[var(--b1)] bg-[var(--bg)] px-5 py-4">
                  <div className="mb-3 flex flex-wrap gap-2">
                    {module.chips.map((chip) => (
                      <span key={chip} className="rounded-pill bg-[var(--bg-2)] px-3 py-1 text-[11px] font-medium text-[var(--t2)]">
                        {chip}
                      </span>
                    ))}
                  </div>
                  <div className="grid gap-2 lg:grid-cols-2">
                    {module.templates.map((template) => (
                      <button
                        key={template}
                        type="button"
                        onClick={() => setQuery(template)}
                        className="group/tpl flex items-center gap-3 rounded-md border border-transparent px-3 py-2.5 text-left transition-all hover:border-[var(--b1)] hover:bg-[var(--bg-w)]"
                      >
                        <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-[var(--bg-2)] text-[11px] text-[var(--t3)] transition-colors group-hover/tpl:bg-[var(--ac-m)] group-hover/tpl:text-[var(--ac)]">
                          ▷
                        </span>
                        <span className="flex-1 text-[12px] text-[var(--t1)]">{template}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </details>
            ))}
          </div>
        </section>

        {error && (
          <div className="mt-8 rounded-lg border border-[var(--red-bg)] bg-[rgba(185,28,28,0.04)] px-4 py-3 text-[13px] text-[var(--red)]">
            {error}
          </div>
        )}

        <div className="gap-fluid-section space-y-10">
          {loading ? (
            <div className="rounded-lg border border-[var(--b1)] bg-[var(--bg-w)] px-5 py-4 text-[13px] text-[var(--t3)] shadow-card">
              正在加载追踪列表和历史分析...
            </div>
          ) : (
            <>
              <PortfolioSummary portfolio={portfolio} loading={loading} />
              <WatchlistGrid items={watchlist} loading={wlLoading} onRefresh={handleRefresh} />

              {history.length > 0 && (
                <section className="space-y-4">
                  <div className="flex items-center gap-3">
                    <h2 className="font-display text-fluid-h2 font-medium tracking-[-0.03em] text-[var(--ink)]">
                      历史分析
                    </h2>
                    <span className="prism-mono-chip">{history.length}</span>
                  </div>

                  <div className="prism-panel overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="min-w-full border-collapse">
                        <thead>
                          <tr className="border-b border-[var(--b2)] bg-[var(--bg-2)]">
                            {["时间", "查询", "代码", "状态"].map((label) => (
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
                          {history.map((item) => {
                            const style = STATUS_STYLE[item.status] || STATUS_STYLE.pending;
                            return (
                              <tr
                                key={item.id}
                                className="cursor-pointer border-b border-[var(--b1)] transition-colors hover:bg-[var(--bg-hover)]"
                                onClick={() => router.push(`/analysis/${item.id}`)}
                              >
                                <td className="px-5 py-4 font-mono text-[12px] text-[var(--t3)]">
                                  {formatDate(item.created_at)}
                                </td>
                                <td className="max-w-[380px] px-5 py-4 text-[14px] text-[var(--t1)]">
                                  <div className="truncate">{item.query}</div>
                                </td>
                                <td className="px-5 py-4 font-mono text-[13px] font-semibold text-[var(--ac)]">
                                  {item.ticker ?? "—"}
                                </td>
                                <td className="px-5 py-4">
                                  <span
                                    className="inline-flex rounded-pill px-3 py-1 text-[11px] font-semibold"
                                    style={{ background: style.bg, color: style.color }}
                                  >
                                    {STATUS_META[item.status] || item.status}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </section>
              )}

              {!watchlist.length && !history.length && (
                <div className="rounded-[20px] border border-dashed border-[var(--b2)] bg-[var(--bg-w)] px-8 py-12 text-center shadow-card">
                  <div className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-[16px] bg-[var(--ac-s)]">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--ac)" strokeWidth="1.6">
                      <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <p className="font-display text-[22px] font-medium text-[var(--ink)]">开始你的第一轮研究</p>
                  <p className="mx-auto mt-3 max-w-[380px] text-[14px] leading-[1.8] text-[var(--t2)]">
                    在搜索框中描述一个具体的投研问题 — 比如 "分析 AAPL 服务业务增长" — Prism 会自动编排数据拉取、估值建模和同业对比的完整流程。
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {["AAPL 财报分析", "NVDA vs AMD 估值", "META 交易策略"].map((hint) => (
                      <button
                        key={hint}
                        type="button"
                        onClick={() => setQuery(hint)}
                        className="rounded-pill border border-[var(--b2)] bg-[var(--bg)] px-4 py-2 text-[12px] font-medium text-[var(--t2)] transition-colors hover:border-[var(--ac-m)] hover:text-[var(--ac)]"
                      >
                        {hint}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
