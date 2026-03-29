"use client";

import { formatCurrency } from "@/utils/formatters";

interface Position {
  ticker: string;
  shares: number;
  avg_cost: number;
  live_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  entry_date: string | null;
}

export interface Portfolio {
  cash: number;
  positions: Position[];
  total_market_value: number;
  total_portfolio_value: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  total_return_pct: number;
  position_count: number;
  win_loss: string;
  invested_pct: number;
}

interface PortfolioSummaryProps {
  portfolio: Portfolio | null;
  loading: boolean;
}

export function PortfolioSummary({ portfolio, loading }: PortfolioSummaryProps) {
  if (loading || !portfolio || portfolio.position_count === 0) return null;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="font-display text-[28px] font-medium tracking-[-0.03em] text-[var(--ink)]">
          模拟仓
        </h2>
        <span className="prism-mono-chip">{portfolio.position_count}</span>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-3 md:grid-cols-4">
        {[
          { label: "组合总值", value: formatCurrency(portfolio.total_portfolio_value) },
          { label: "现金", value: formatCurrency(portfolio.cash) },
          {
            label: "总回报",
            value: `${portfolio.total_return_pct >= 0 ? "+" : ""}${portfolio.total_return_pct.toFixed(2)}%`,
            color: portfolio.total_return_pct >= 0 ? "var(--green)" : "var(--red)",
          },
          { label: "已投资", value: `${portfolio.invested_pct.toFixed(1)}%` },
        ].map((item) => (
          <div key={item.label} className="prism-panel p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
              {item.label}
            </div>
            <div
              className="mt-2 font-mono text-[20px] font-semibold"
              style={{ color: "color" in item && item.color ? item.color : "var(--cy-t)" }}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Positions Table */}
      <div className="prism-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="border-b border-[var(--b2)] bg-[var(--bg-2)]">
                {["代码", "股数", "成本", "现价", "市值", "盈亏"].map((label, index) => (
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
              {portfolio.positions.map((pos) => (
                <tr key={pos.ticker} className="border-b border-[var(--b1)] last:border-b-0">
                  <td className="px-5 py-4 font-mono text-[13px] font-semibold text-[var(--ac)]">
                    {pos.ticker}
                  </td>
                  <td className="px-5 py-4 font-mono text-[13px] text-[var(--t2)]">{pos.shares}</td>
                  <td className="px-5 py-4 text-right font-mono text-[13px] text-[var(--t2)]">
                    {formatCurrency(pos.avg_cost)}
                  </td>
                  <td className="px-5 py-4 text-right font-mono text-[13px] text-[var(--cy-t)]">
                    {pos.live_price != null ? formatCurrency(pos.live_price) : "—"}
                  </td>
                  <td className="px-5 py-4 text-right font-mono text-[13px] text-[var(--cy-t)]">
                    {formatCurrency(pos.market_value)}
                  </td>
                  <td
                    className="px-5 py-4 text-right font-mono text-[13px] font-semibold"
                    style={{ color: pos.unrealized_pnl >= 0 ? "var(--green)" : "var(--red)" }}
                  >
                    {pos.unrealized_pnl >= 0 ? "+" : ""}
                    {pos.unrealized_pnl_pct.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
