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

function getCellStyle(
  value: number,
  baseValue: number,
  isBase: boolean
): { bg: string; text: string; border?: string } {
  if (isBase) {
    return {
      bg: "rgba(245,128,37,0.12)",
      text: "var(--iris-text)",
      border: "1px solid var(--iris-accent)",
    };
  }

  if (isNaN(value) || isNaN(baseValue)) return { bg: "transparent", text: "var(--iris-text-muted)" };
  const diff = baseValue !== 0 ? ((value - baseValue) / baseValue) * 100 : 0;

  if (diff > 20) return { bg: "rgba(34,197,94,0.25)", text: "#4ade80" };
  if (diff > 10) return { bg: "rgba(34,197,94,0.15)", text: "#86efac" };
  if (diff > 5) return { bg: "rgba(34,197,94,0.08)", text: "#bbf7d0" };
  if (diff > 0) return { bg: "rgba(34,197,94,0.04)", text: "var(--iris-text-secondary)" };
  if (diff > -5) return { bg: "rgba(239,68,68,0.04)", text: "var(--iris-text-secondary)" };
  if (diff > -10) return { bg: "rgba(239,68,68,0.08)", text: "#fca5a5" };
  if (diff > -20) return { bg: "rgba(239,68,68,0.15)", text: "#f87171" };
  return { bg: "rgba(239,68,68,0.25)", text: "#ef4444" };
}

export function SensitivityHeatmap({
  data,
  rowLabel,
  colLabel,
  rowValues,
  colValues,
}: SensitivityHeatmapProps) {
  if (data.length === 0) return null;

  const baseCell = data.find((c) => c.isBase);
  const baseValue =
    baseCell?.value ?? data[Math.floor(data.length / 2)]?.value ?? 0;

  const cellMap = new Map<string, SensitivityCell>();
  data.forEach((cell) => cellMap.set(`${cell.row}-${cell.col}`, cell));

  return (
    <div className="overflow-hidden border border-[var(--iris-border)]">
      <div className="p-[5px_8px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <span className="font-mono text-[11px] text-[var(--iris-accent)] uppercase tracking-[0.08em]">
          Sensitivity Analysis
        </span>
        <span className="font-mono text-[10px] text-[var(--iris-text-muted)] ml-2">
          {rowLabel} vs {colLabel}
        </span>
      </div>
      <div className="grid gap-[1px] p-[6px]" style={{ gridTemplateColumns: `auto repeat(${colValues.length}, 1fr)` }}>
        {/* Header row */}
        <div className="p-[3px] font-mono text-[10px] text-[var(--iris-text-muted)]">
          {rowLabel}\{colLabel}
        </div>
        {colValues.map((col) => (
          <div
            key={col}
            className="p-[3px] text-center font-mono text-[10px] text-[var(--iris-accent)]"
            style={{ opacity: 0.7 }}
          >
            {col}
          </div>
        ))}

        {/* Data rows */}
        {rowValues.map((row) => (
          <React.Fragment key={row}>
            <div
              className="p-[3px] font-mono text-[10px] text-[var(--iris-accent)]"
              style={{ opacity: 0.7 }}
            >
              {row}
            </div>
            {colValues.map((col) => {
              const cell = cellMap.get(`${row}-${col}`);
              const value = Number(cell?.value ?? 0);
              const isBase = cell?.isBase ?? false;
              const style = getCellStyle(value, baseValue, isBase);

              return (
                <div
                  key={`${row}-${col}`}
                  className="p-[3px] text-center font-mono text-[10px]"
                  style={{
                    backgroundColor: style.bg,
                    color: style.text,
                    fontWeight: isBase ? 700 : 400,
                    border: style.border || "none",
                  }}
                >
                  {isNaN(value) ? "—" : `$${value.toFixed(0)}`}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
