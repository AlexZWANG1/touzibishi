"use client";

import type { FinancialTableData } from "@/types/analysis";

interface FinancialTableProps {
  table: FinancialTableData;
}

function isNegativeValue(val: string | number): boolean {
  if (typeof val === "number") return val < 0;
  if (typeof val === "string") {
    const cleaned = val.replace(/[,$%\s]/g, "");
    if (cleaned.startsWith("(") && cleaned.endsWith(")")) return true;
    return parseFloat(cleaned) < 0;
  }
  return false;
}

export function FinancialTable({ table }: FinancialTableProps) {
  return (
    <div className="overflow-hidden border border-[var(--iris-border)]">
      {/* Title bar */}
      <div className="p-[5px_8px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <h3 className="font-mono text-[11px] text-[var(--iris-accent)] uppercase tracking-[0.08em]">
          {table.title}
        </h3>
      </div>

      {/* Scrollable table area */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
              <th className="sticky left-0 bg-[var(--iris-surface)] p-[3px_8px] text-left font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]">
                {table.headers[0] || ""}
              </th>
              {table.headers.slice(1).map((header) => (
                <th
                  key={header}
                  className="p-[3px_8px] text-right font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--iris-accent)]"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, idx) => {
              const isLast = idx === table.rows.length - 1;

              return (
                <tr
                  key={idx}
                  style={{
                    borderBottom: isLast ? "none" : "1px solid rgba(30,32,48,0.3)",
                  }}
                >
                  <td
                    className={`sticky left-0 p-[3px_8px] font-mono ${
                      row.isHeader
                        ? "text-[10px] uppercase tracking-[0.06em] text-[var(--iris-text-muted)] bg-[var(--iris-surface)]"
                        : row.isBold
                          ? "font-semibold text-[var(--iris-text)]"
                          : "text-[var(--iris-text-secondary)]"
                    }`}
                    style={{
                      paddingLeft: row.indent
                        ? `${8 + row.indent * 12}px`
                        : undefined,
                      background: row.isHeader
                        ? undefined
                        : "var(--iris-bg)",
                    }}
                  >
                    {row.label}
                  </td>
                  {row.values.map((val, vIdx) => {
                    const negative = isNegativeValue(val);
                    return (
                      <td
                        key={vIdx}
                        className={`p-[3px_8px] text-right font-mono ${
                          row.isHeader
                            ? "text-[10px] text-[var(--iris-text-muted)]"
                            : negative
                              ? "text-[#EF4444]"
                              : row.isBold
                                ? "font-semibold text-[var(--iris-text)]"
                                : "text-[var(--iris-text-secondary)]"
                        }`}
                      >
                        {val}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
