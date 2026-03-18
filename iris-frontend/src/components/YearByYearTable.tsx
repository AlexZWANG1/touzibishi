"use client";

import type { YearProjection } from "@/types/analysis";
import { formatNumber, formatPercent } from "@/utils/formatters";

interface YearByYearTableProps {
  data: YearProjection[];
}

export function YearByYearTable({ data }: YearByYearTableProps) {
  if (data.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">逐年预测</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
              <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                年份
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                收入
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                增速
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                EBITDA
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                利润率
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                FCF
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={row.year}
                className="border-b border-[var(--iris-border)] last:border-0 hover:bg-[var(--iris-surface-hover)]"
              >
                <td className="px-4 py-2 font-medium text-[var(--iris-text)]">
                  {row.year}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {formatNumber(row.revenue)}
                </td>
                <td
                  className={`px-3 py-2 text-right font-mono ${
                    row.growth >= 0
                      ? "text-[var(--status-bullish)]"
                      : "text-[var(--status-bearish)]"
                  }`}
                >
                  {formatPercent(row.growth)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {formatNumber(row.ebitda)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {row.margin.toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--iris-text-secondary)]">
                  {formatNumber(row.fcf)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
