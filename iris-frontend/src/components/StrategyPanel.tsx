"use client";

import { useState } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { formatCurrency, formatPercent } from "@/utils/formatters";

const API = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");

const ACTION_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  BUY: { bg: "var(--green-bg)", color: "var(--green)", label: "买入" },
  HOLD: { bg: "var(--amber-bg)", color: "var(--amber)", label: "持有" },
  WATCH: { bg: "var(--amber-bg)", color: "var(--amber)", label: "观察" },
  TRIM: { bg: "var(--red-bg)", color: "var(--red)", label: "减仓" },
  SELL: { bg: "var(--red-bg)", color: "var(--red)", label: "卖出" },
};

export function StrategyPanel() {
  const strategy = useAnalysisStore((s) => s.strategyPanel);
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState<string | null>(null);

  const handleExecute = async () => {
    if (!strategy.signal) return;
    const { ticker, action, suggestedShares, price } = strategy.signal;
    if (!suggestedShares || suggestedShares <= 0) return;

    setExecuting(true);
    setExecResult(null);
    try {
      const tradeAction = action === "TRIM" ? "SELL" : action;
      const res = await fetch(`${API}/api/trade/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          action: tradeAction,
          shares: suggestedShares,
          price,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setExecResult(`失败: ${err.detail || "未知错误"}`);
      } else {
        setExecResult("交易已执行");
      }
    } catch {
      setExecResult("网络错误");
    } finally {
      setExecuting(false);
    }
  };

  if (!strategy.signal && !strategy.portfolio) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t4)]">策略面板</div>
        <p className="mt-2 text-[13px] text-[var(--t3)]">交易信号、组合摘要和校准数据生成后，会展示在这里。</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      {/* Trade Signal Card */}
      {strategy.signal && (
        <section className="prism-panel p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="inline-flex rounded-pill px-3 py-1 text-[11px] font-semibold"
              style={{
                background: ACTION_STYLES[strategy.signal.action]?.bg || "var(--bg-2)",
                color: ACTION_STYLES[strategy.signal.action]?.color || "var(--t2)",
              }}
            >
              {ACTION_STYLES[strategy.signal.action]?.label || strategy.signal.action}
            </span>
            <span className="font-mono text-[13px] font-semibold text-[var(--ac)]">
              {strategy.signal.ticker}
            </span>
            {strategy.signal.riskRewardRatio != null && strategy.signal.riskRewardRatio > 0 && (
              <span
                className="rounded-pill px-3 py-1 font-mono text-[11px] font-semibold"
                style={{
                  background: strategy.signal.riskRewardRatio >= 2 ? "var(--green-bg)" : strategy.signal.riskRewardRatio >= 1.5 ? "var(--amber-bg)" : "var(--red-bg)",
                  color: strategy.signal.riskRewardRatio >= 2 ? "var(--green)" : strategy.signal.riskRewardRatio >= 1.5 ? "var(--amber)" : "var(--red)",
                }}
              >
                R:R {strategy.signal.riskRewardRatio}:1
              </span>
            )}
          </div>

          {/* Key Metrics */}
          <div className="mt-4 grid gap-3 sm:grid-cols-[1.2fr_0.8fr_0.8fr]">
            <div className="rounded-lg bg-[var(--bg)] p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                现价
              </div>
              <div className="mt-2 font-mono text-[28px] font-semibold text-[var(--cy-t)]">
                {formatCurrency(strategy.signal.price)}
              </div>
            </div>
            {strategy.signal.targetPrice > 0 && (
              <div className="rounded-lg bg-[var(--bg)] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                  目标价
                </div>
                <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--green)]">
                  {formatCurrency(strategy.signal.targetPrice)}
                </div>
              </div>
            )}
            {strategy.signal.stopLoss > 0 && (
              <div className="rounded-lg bg-[var(--bg)] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                  止损价
                </div>
                <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--red)]">
                  {formatCurrency(strategy.signal.stopLoss)}
                </div>
              </div>
            )}
            {strategy.signal.positionPct > 0 && (
              <div className="rounded-lg bg-[var(--bg)] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                  建议仓位
                </div>
                <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--cy-t)]">
                  {strategy.signal.positionPct.toFixed(1)}%
                </div>
              </div>
            )}
          </div>

          {/* Reasoning */}
          <p className="mt-4 text-[14px] leading-[1.8] text-[var(--t2)]">
            {strategy.signal.reasoning}
          </p>

          {/* Catalysts */}
          {strategy.signal.catalysts && (
            <div className="mt-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                催化剂
              </span>
              <p className="mt-1 text-[13px] text-[var(--t2)]">{strategy.signal.catalysts}</p>
            </div>
          )}

          {/* Warnings */}
          {strategy.signal.warnings && strategy.signal.warnings.length > 0 && (
            <div className="mt-4 space-y-2">
              {strategy.signal.warnings.map((w, i) => (
                <div key={i} className="rounded-md bg-[var(--amber-bg)] px-4 py-2.5 text-[12px] leading-[1.6] text-[var(--amber)]">
                  {w}
                </div>
              ))}
            </div>
          )}

          {/* Execute Button */}
          {(strategy.signal.action === "BUY" || strategy.signal.action === "SELL" || strategy.signal.action === "TRIM") &&
            strategy.signal.suggestedShares > 0 && (
              <div className="mt-5 flex items-center gap-3">
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  className="rounded-lg px-5 py-2.5 text-[13px] font-semibold text-white transition-opacity disabled:opacity-50"
                  style={{
                    backgroundColor:
                      strategy.signal.action === "BUY" ? "var(--green)" : "var(--red)",
                  }}
                >
                  {executing
                    ? "执行中..."
                    : `确认${ACTION_STYLES[strategy.signal.action]?.label || strategy.signal.action} ${strategy.signal.suggestedShares} 股`}
                </button>
                {execResult && (
                  <span className="text-[13px] text-[var(--t2)]">{execResult}</span>
                )}
              </div>
            )}
        </section>
      )}

      {/* Portfolio Summary */}
      {strategy.portfolio && (
        <section className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            {[
              { label: "组合总值", value: formatCurrency(strategy.portfolio.totalPortfolioValue) },
              { label: "现金", value: formatCurrency(strategy.portfolio.cash) },
              { label: "总回报", value: formatPercent(strategy.portfolio.totalReturnPct) },
              { label: "已投资", value: `${strategy.portfolio.investedPct.toFixed(1)}%` },
            ].map((item) => (
              <div key={item.label} className="prism-panel p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                  {item.label}
                </div>
                <div className="mt-2 font-mono text-[20px] font-semibold text-[var(--cy-t)]">
                  {item.value}
                </div>
              </div>
            ))}
          </div>

          <div className="prism-panel overflow-hidden">
            <div className="border-b border-[var(--b1)] px-5 py-4">
              <h3 className="text-[15px] font-semibold text-[var(--t1)]">模拟仓位</h3>
              <p className="mt-1 text-[12px] text-[var(--t3)]">
                {strategy.portfolio.positionCount} 个持仓 · {strategy.portfolio.winLoss}
              </p>
            </div>
            {strategy.portfolio.positions.length === 0 ? (
              <div className="px-5 py-8 text-[13px] text-[var(--t3)]">当前没有持仓。</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--b1)] bg-[var(--bg-2)]">
                      {["代码", "股数", "成本", "现价", "市值", "盈亏"].map((label) => (
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
                    {strategy.portfolio.positions.map((position) => (
                      <tr key={position.ticker} className="border-b border-[var(--b1)] last:border-b-0">
                        <td className="px-5 py-4 font-mono text-[13px] font-semibold text-[var(--ac)]">
                          {position.ticker}
                        </td>
                        <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">{position.shares}</td>
                        <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">
                          {formatCurrency(position.avgCost)}
                        </td>
                        <td className="px-5 py-4 font-mono text-[13px] text-[var(--cy-t)]">
                          {position.livePrice != null ? formatCurrency(position.livePrice) : "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-[13px] text-[var(--cy-t)]">
                          {formatCurrency(position.marketValue)}
                        </td>
                        <td
                          className="px-5 py-4 font-mono text-[13px] font-semibold"
                          style={{ color: position.unrealizedPnl >= 0 ? "var(--green)" : "var(--red)" }}
                        >
                          {position.unrealizedPnl >= 0 ? "+" : ""}
                          {position.unrealizedPnlPct.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
