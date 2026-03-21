"use client";

import type { FinancialTableData } from "@/types/analysis";

interface FinancialTableProps {
  table: FinancialTableData;
}

function isNegativeValue(value: string | number): boolean {
  if (typeof value === "number") return value < 0;
  const cleaned = value.replace(/[,$%\s]/g, "");
  if (cleaned.startsWith("(") && cleaned.endsWith(")")) return true;
  return Number.parseFloat(cleaned) < 0;
}

export function FinancialTable({ table }: FinancialTableProps) {
  return (
    <div className="prism-panel overflow-hidden">
      <div className="border-b border-[var(--b1)] px-5 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--t1)]">{table.title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="border-b border-[var(--b1)] bg-[var(--bg-2)]">
              {table.headers.map((header, index) => (
                <th
                  key={`${header}-${index}`}
                  className="px-5 py-3 text-left font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]"
                  style={{ textAlign: index === 0 ? "left" : "right" }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={`${row.label}-${rowIndex}`} className="border-b border-[var(--b1)] last:border-b-0">
                <td className="px-5 py-3 text-[14px] font-medium text-[var(--t1)]">{row.label}</td>
                {row.values.map((value, valueIndex) => (
                  <td
                    key={`${row.label}-${valueIndex}`}
                    className="px-5 py-3 text-right font-mono text-[13px]"
                    style={{
                      color: isNegativeValue(value) ? "var(--red)" : "var(--t2)",
                      fontWeight: row.isBold ? 600 : 500,
                    }}
                  >
                    {value}
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
