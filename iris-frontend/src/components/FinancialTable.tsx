"use client";

import type { FinancialTableData } from "@/types/analysis";

interface FinancialTableProps {
  table: FinancialTableData;
}

export function FinancialTable({ table }: FinancialTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">{table.title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
              <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
                项目
              </th>
              {table.headers.map((header) => (
                <th
                  key={header}
                  className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, idx) => (
              <tr
                key={idx}
                className={`border-b border-[var(--iris-border)] last:border-0 ${
                  row.isHeader ? "bg-[var(--iris-surface)]" : "hover:bg-[var(--iris-surface-hover)]"
                }`}
              >
                <td
                  className={`px-4 py-2 ${
                    row.isBold ? "font-semibold text-[var(--iris-text)]" : "text-[var(--iris-text-secondary)]"
                  }`}
                  style={{ paddingLeft: row.indent ? `${16 + row.indent * 16}px` : undefined }}
                >
                  {row.label}
                </td>
                {row.values.map((val, vIdx) => (
                  <td
                    key={vIdx}
                    className={`px-3 py-2 text-right font-mono ${
                      row.isBold ? "font-semibold text-[var(--iris-text)]" : "text-[var(--iris-text-secondary)]"
                    }`}
                  >
                    {val}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
