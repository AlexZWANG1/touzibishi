"use client";

import type { YearProjection } from "@/types/analysis";
import { formatNumber, formatPercent } from "@/utils/formatters";

interface YearByYearTableProps {
  data: YearProjection[];
}

export function YearByYearTable({ data }: YearByYearTableProps) {
  if (data.length === 0) return null;

  return (
    <div className="overflow-hidden border border-[var(--iris-border)]">
      <div className="p-[5px_8px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <h3 className="font-mono text-[11px] text-[var(--iris-accent)] uppercase tracking-[0.08em]">
          Year-by-Year Projections
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
              <th className="sticky left-0 bg-[var(--iris-surface)] p-[3px_8px] text-left font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                Year
              </th>
              <th className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                Revenue
              </th>
              <th className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                Growth
              </th>
              <th className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                EBITDA
              </th>
              <th className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                Margin
              </th>
              <th className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                FCF
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => {
              const isLast = idx === data.length - 1;
              return (
                <tr
                  key={row.year}
                  style={{
                    borderBottom: isLast ? "none" : "1px solid rgba(30,32,48,0.3)",
                  }}
                >
                  <td
                    className={`sticky left-0 p-[3px_8px] font-mono font-medium text-[var(--iris-text)] ${isLast ? "font-semibold" : ""}`}
                    style={{ background: "var(--iris-bg)" }}
                  >
                    {row.year}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-text-secondary)]">
                    {formatNumber(row.revenue)}
                  </td>
                  <td
                    className={`p-[3px_8px] text-right font-mono ${
                      row.growth >= 0
                        ? "text-[#22C55E]"
                        : "text-[#EF4444]"
                    }`}
                  >
                    {formatPercent(row.growth)}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-text-secondary)]">
                    {formatNumber(row.ebitda)}
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-text-secondary)]">
                    {row.margin.toFixed(1)}%
                  </td>
                  <td className="p-[3px_8px] text-right font-mono text-[var(--iris-text-secondary)]">
                    {formatNumber(row.fcf)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
