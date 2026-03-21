"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchBar, type AnalysisMode } from "@/components/SearchBar";
import { WatchlistGrid } from "@/components/WatchlistGrid";
import { PrismLogo } from "@/components/PrismLogo";
import type { WatchlistItem, HistoryItem } from "@/types/analysis";
import { getHistory, getWatchlist, startAnalysis } from "@/utils/api";
import { classNames } from "@/utils/formatters";

const ONBOARDING_STORAGE_KEY = "prism-onboarding-dismissed";

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
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [wlLoading, setWlLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<AnalysisMode>("analysis");
  const [searchLoading, setSearchLoading] = useState(false);
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);
  const router = useRouter();

  useEffect(() => {
    try {
      setOnboardingDismissed(window.localStorage.getItem(ONBOARDING_STORAGE_KEY) === "1");
    } catch {
      setOnboardingDismissed(false);
    }
  }, []);

  useEffect(() => {
    async function load() {
      try {
        const [watchlistResult, historyResult] = await Promise.allSettled([
          getWatchlist(),
          getHistory(),
        ]);

        if (watchlistResult.status === "fulfilled") {
          setWatchlist(watchlistResult.value);
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
      const result = await getWatchlist();
      setWatchlist(result);
    } catch (refreshError) {
      console.error("Failed to refresh watchlist:", refreshError);
      setError("刷新 watchlist 失败。");
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

  const dismissOnboarding = useCallback(() => {
    setOnboardingDismissed(true);
    try {
      window.localStorage.setItem(ONBOARDING_STORAGE_KEY, "1");
    } catch {
      // ignore localStorage failures
    }
  }, []);

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="mx-auto max-w-[980px] px-5 pb-20 pt-10 sm:px-8">
        <section className="animate-fade-up">
          <div className="prism-kicker">Prism Research Intelligence</div>
          <div className="mt-5 grid gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <h1 className="max-w-[700px] font-display text-[42px] leading-[1.04] tracking-[-0.04em] text-[var(--ink)] sm:text-[54px]">
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

        {!onboardingDismissed && (
          <aside className="prism-card mt-6 flex gap-4 border-[rgba(99,102,241,0.08)] bg-[linear-gradient(135deg,rgba(99,102,241,0.03)_0%,rgba(6,182,212,0.03)_52%,rgba(16,185,129,0.02)_100%)] p-5 animate-fade-up [animation-delay:180ms]">
            <div className="mt-0.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--ac-s)] text-[var(--ac)]">
                <PrismLogo size={18} showWordmark={false} />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-[13px] font-semibold text-[var(--t1)]">
                Prism 是一个独立的 AI Research Harness
              </div>
              <p className="mt-1 text-[13px] leading-[1.75] text-[var(--t2)]">
                它会自动编排多步研究流程：<strong>拉取财务数据 → 搜索最新资讯 → 构建估值模型 → 对比同业 → 生成交易建议</strong>。你只需要描述研究目标，Prism 会选择合适的工具并实时展示中间过程。分析过程中你可以随时引导方向。
              </p>
            </div>
            <button
              type="button"
              onClick={dismissOnboarding}
              className="self-start rounded-md p-1.5 text-[var(--t3)] transition-colors hover:bg-white/60 hover:text-[var(--t1)]"
              aria-label="关闭引导"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </aside>
        )}

        <section className="mt-8 space-y-4 animate-fade-up [animation-delay:240ms]">
          {CAPABILITY_MODULES.map((module) => (
            <article key={module.key} className="prism-card overflow-hidden">
              <div className="h-[3px]" style={{ background: module.bar }} />
              <div className="flex flex-col gap-5 p-6 lg:flex-row lg:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <CapabilityIcon path={module.iconPath} style={module.iconStyle} />
                    <div>
                      <h2 className="text-[16px] font-semibold text-[var(--t1)]">{module.title}</h2>
                      <p className="mt-1 text-[13px] leading-[1.7] text-[var(--t2)]">{module.description}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {module.chips.map((chip) => (
                      <span key={chip} className="rounded-pill bg-[var(--bg-2)] px-3 py-1 text-[11px] font-medium text-[var(--t2)]">
                        {chip}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="grid gap-2 lg:w-[320px] lg:shrink-0">
                  {module.templates.map((template) => (
                    <button
                      key={template}
                      type="button"
                      onClick={() => setQuery(template)}
                      className="group flex items-center gap-3 rounded-md border border-transparent px-4 py-3 text-left transition-all hover:border-[var(--b1)] hover:bg-[var(--bg-hover)]"
                    >
                      <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-[var(--bg-2)] text-[var(--t3)] transition-colors group-hover:bg-[var(--ac-m)] group-hover:text-[var(--ac)]">
                        ▷
                      </span>
                      <span className="flex-1 text-[13px] font-medium text-[var(--t1)]">{template}</span>
                      <span className="translate-x-[-4px] text-[13px] text-[var(--t4)] opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100">
                        →
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </section>

        {error && (
          <div className="mt-8 rounded-lg border border-[var(--red-bg)] bg-[rgba(185,28,28,0.04)] px-4 py-3 text-[13px] text-[var(--red)]">
            {error}
          </div>
        )}

        <div className="mt-10 space-y-10">
          {loading ? (
            <div className="rounded-lg border border-[var(--b1)] bg-[var(--bg-w)] px-5 py-4 text-[13px] text-[var(--t3)] shadow-card">
              正在加载 watchlist 和历史分析...
            </div>
          ) : (
            <>
              <WatchlistGrid items={watchlist} loading={wlLoading} onRefresh={handleRefresh} />

              {history.length > 0 && (
                <section className="space-y-4">
                  <div className="flex items-center gap-3">
                    <h2 className="font-display text-[28px] font-medium tracking-[-0.03em] text-[var(--ink)]">
                      Recent Analyses
                    </h2>
                    <span className="prism-mono-chip">{history.length}</span>
                  </div>

                  <div className="prism-panel overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="min-w-full border-collapse">
                        <thead>
                          <tr className="border-b border-[var(--b2)] bg-[var(--bg-2)]">
                            {["Date", "Query", "Ticker", "Status", "Tokens"].map((label, index) => (
                              <th
                                key={label}
                                className="px-5 py-3 text-left font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]"
                                style={{ textAlign: index === 4 ? "right" : "left" }}
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
                                <td className="px-5 py-4 text-right font-mono text-[12px] text-[var(--t2)]">
                                  {(item.tokens_in + item.tokens_out).toLocaleString()}
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
                <div className="rounded-[20px] border border-[var(--b1)] bg-[var(--bg-w)] px-6 py-8 text-center shadow-card">
                  <p className="text-[15px] font-medium text-[var(--t1)]">还没有保存的研究结果</p>
                  <p className="mt-2 text-[13px] leading-[1.7] text-[var(--t3)]">
                    从上面的主输入框开始描述一个研究任务，Prism 会建立你的第一个工作区。
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
