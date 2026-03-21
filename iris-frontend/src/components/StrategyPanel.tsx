"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";
import { formatCurrency, formatPercent } from "@/utils/formatters";

const ACTION_STYLES: Record<string, { bg: string; color: string }> = {
  BUY: { bg: "var(--green-bg)", color: "var(--green)" },
  HOLD: { bg: "var(--amber-bg)", color: "var(--amber)" },
  WATCH: { bg: "var(--amber-bg)", color: "var(--amber)" },
  TRIM: { bg: "var(--red-bg)", color: "var(--red)" },
  SELL: { bg: "var(--red-bg)", color: "var(--red)" },
  NO_ENTRY: { bg: "var(--bg-2)", color: "var(--t2)" },
};

export function StrategyPanel() {
  const strategy = useAnalysisStore((s) => s.strategyPanel);
  const memory = useAnalysisStore((s) => s.memoryPanel);

  const hasCalibration =
    memory.calibrationHits > 0 ||
    memory.calibrationMisses > 0 ||
    memory.recentRecalls.length > 0;

  if (!strategy.signal && !strategy.portfolio && !hasCalibration) {
    return (
      <div className="px-6 py-8 text-[13px] text-[var(--t3)]">
        等待交易信号、组合摘要或校准数据...
      </div>
    );
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      {strategy.signal && (
        <section className="prism-panel p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="inline-flex rounded-pill px-3 py-1 text-[11px] font-semibold"
              style={ACTION_STYLES[strategy.signal.action] || ACTION_STYLES.NO_ENTRY}
            >
              {strategy.signal.action}
            </span>
            <span className="font-mono text-[13px] font-semibold text-[var(--ac)]">
              {strategy.signal.ticker}
            </span>
            <span className="rounded-pill bg-[var(--bg-2)] px-3 py-1 text-[11px] font-medium text-[var(--t2)]">
              {strategy.signal.signalStrength}
            </span>
            {strategy.signal.conviction && (
              <span className="rounded-pill bg-[var(--ac-s)] px-3 py-1 text-[11px] font-medium text-[var(--ac)]">
                {strategy.signal.conviction}
              </span>
            )}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-[var(--bg)] p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Target Weight
              </div>
              <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--cy-t)]">
                {(strategy.signal.targetWeight * 100).toFixed(1)}%
              </div>
            </div>
            <div className="rounded-lg bg-[var(--bg)] p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Discount
              </div>
              <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--cy-t)]">
                {strategy.signal.discountPct != null ? `${strategy.signal.discountPct.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div className="rounded-lg bg-[var(--bg)] p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Suggested Shares
              </div>
              <div className="mt-2 font-mono text-[22px] font-semibold text-[var(--cy-t)]">
                {strategy.signal.suggestedShares ?? "—"}
              </div>
            </div>
          </div>

          <p className="mt-4 text-[14px] leading-[1.8] text-[var(--t2)]">{strategy.signal.reasoning}</p>

          {strategy.signal.constraintChecks.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Constraint Checks
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {strategy.signal.constraintChecks.map((check) => (
                  <span key={check} className="rounded-pill bg-[var(--bg-2)] px-3 py-1 text-[11px] text-[var(--t2)]">
                    {check}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {strategy.portfolio && (
        <section className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            {[
              { label: "Portfolio Value", value: formatCurrency(strategy.portfolio.totalPortfolioValue) },
              { label: "Cash", value: formatCurrency(strategy.portfolio.cash) },
              { label: "Total Return", value: formatPercent(strategy.portfolio.totalReturnPct) },
              { label: "Invested", value: `${strategy.portfolio.investedPct.toFixed(1)}%` },
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
              <h3 className="text-[15px] font-semibold text-[var(--t1)]">Paper Portfolio</h3>
              <p className="mt-1 text-[12px] text-[var(--t3)]">
                {strategy.portfolio.positionCount} positions · {strategy.portfolio.winLoss}
              </p>
            </div>
            {strategy.portfolio.positions.length === 0 ? (
              <div className="px-5 py-8 text-[13px] text-[var(--t3)]">当前组合没有持仓。</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--b1)] bg-[var(--bg-2)]">
                      {["Ticker", "Shares", "Avg Cost", "Live", "Market Value", "PnL"].map((label) => (
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

      {hasCalibration && (
        <section className="prism-panel p-5">
          <h3 className="text-[15px] font-semibold text-[var(--t1)]">Calibration Summary</h3>
          <div className="mt-4">
            <CalibrationSummary
              hits={memory.calibrationHits}
              misses={memory.calibrationMisses}
              recentRecalls={memory.recentRecalls}
            />
          </div>
        </section>
      )}
    </div>
  );
}
