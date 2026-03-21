"use client";

import React from "react";
import type { SensitivityCell } from "@/types/analysis";

interface SensitivityHeatmapProps {
  data: SensitivityCell[];
  rowLabel: string;
  colLabel: string;
  rowValues: string[];
  colValues: string[];
}

function getCellStyle(value: number, baseValue: number, isBase: boolean) {
  if (isBase) {
    return {
      bg: "var(--ac-m)",
      color: "var(--ac-t)",
      border: "1px solid var(--ac)",
      weight: 700,
    };
  }

  const diff = baseValue !== 0 ? ((value - baseValue) / baseValue) * 100 : 0;

  if (diff > 18) return { bg: "var(--green-bg)", color: "var(--green)", border: "none", weight: 600 };
  if (diff > 8) return { bg: "rgba(21,128,61,0.035)", color: "var(--t2)", border: "none", weight: 500 };
  if (diff > -8) return { bg: "var(--bg-2)", color: "var(--t2)", border: "none", weight: 500 };
  if (diff > -18) return { bg: "rgba(185,28,28,0.035)", color: "var(--t2)", border: "none", weight: 500 };
  return { bg: "var(--red-bg)", color: "var(--red)", border: "none", weight: 600 };
}

export function SensitivityHeatmap({
  data,
  rowLabel,
  colLabel,
  rowValues,
  colValues,
}: SensitivityHeatmapProps) {
  if (data.length === 0) return null;

  const baseCell = data.find((cell) => cell.isBase);
  const baseValue = baseCell?.value ?? data[Math.floor(data.length / 2)]?.value ?? 0;
  const cellMap = new Map<string, SensitivityCell>();
  data.forEach((cell) => cellMap.set(`${cell.row}-${cell.col}`, cell));

  return (
    <div className="prism-panel overflow-hidden">
      <div className="border-b border-[var(--b1)] px-5 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--t1)]">Sensitivity</h3>
        <p className="mt-1 text-[12px] text-[var(--t3)]">
          {rowLabel} vs {colLabel}
        </p>
      </div>

      <div className="overflow-x-auto p-4">
        <div
          className="grid gap-[8px]"
          style={{ gridTemplateColumns: `auto repeat(${colValues.length}, minmax(72px, 1fr))` }}
        >
          <div className="px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
            {rowLabel}\{colLabel}
          </div>
          {colValues.map((col) => (
            <div
              key={col}
              className="px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]"
            >
              {col}
            </div>
          ))}

          {rowValues.map((row) => (
            <React.Fragment key={row}>
              <div className="px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                {row}
              </div>
              {colValues.map((col) => {
                const cell = cellMap.get(`${row}-${col}`);
                const value = Number(cell?.value ?? 0);
                const style = getCellStyle(value, baseValue, cell?.isBase ?? false);

                return (
                  <div
                    key={`${row}-${col}`}
                    className="rounded-md px-3 py-3.5 text-center font-mono text-[12px]"
                    style={{
                      background: style.bg,
                      color: style.color,
                      border: style.border,
                      fontWeight: style.weight,
                    }}
                  >
                    {Number.isNaN(value) ? "—" : `$${value.toFixed(0)}`}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
