"use client";

import type { YearProjection } from "@/types/analysis";
import { formatNumber, formatPercent } from "@/utils/formatters";

interface YearByYearTableProps {
  data: YearProjection[];
}

export function YearByYearTable({ data }: YearByYearTableProps) {
  if (data.length === 0) return null;

  return (
    <div className="prism-panel overflow-hidden">
      <div className="border-b border-[var(--b1)] px-5 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--t1)]">Year-by-Year Projections</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="border-b border-[var(--b1)] bg-[var(--bg-2)]">
              {["Year", "Revenue", "Growth", "EBITDA", "Margin", "FCF"].map((label) => (
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
            {data.map((row) => (
              <tr key={row.year} className="border-b border-[var(--b1)] last:border-b-0">
                <td className="px-5 py-3 text-[14px] font-medium text-[var(--t1)]">{row.year}</td>
                <td className="px-5 py-3 font-mono text-[13px] text-[var(--t2)]">{formatNumber(row.revenue)}</td>
                <td
                  className="px-5 py-3 font-mono text-[13px] font-semibold"
                  style={{ color: row.growth >= 0 ? "var(--green)" : "var(--red)" }}
                >
                  {formatPercent(row.growth)}
                </td>
                <td className="px-5 py-3 font-mono text-[13px] text-[var(--t2)]">{formatNumber(row.ebitda)}</td>
                <td className="px-5 py-3 font-mono text-[13px] text-[var(--t2)]">{row.margin.toFixed(1)}%</td>
                <td className="px-5 py-3 font-mono text-[13px] text-[var(--t2)]">{formatNumber(row.fcf)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
