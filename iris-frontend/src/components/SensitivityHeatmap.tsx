"use client";

import type { SensitivityCell } from "@/types/analysis";

interface SensitivityHeatmapProps {
  data: SensitivityCell[];
  rowLabel: string;
  colLabel: string;
  rowValues: string[];
  colValues: string[];
}

function getCellColor(value: number, baseValue: number): string {
  const diff = ((value - baseValue) / baseValue) * 100;
  if (diff > 20) return "bg-green-500/30 text-green-300";
  if (diff > 10) return "bg-green-500/20 text-green-400";
  if (diff > 0) return "bg-green-500/10 text-green-400";
  if (diff > -10) return "bg-red-500/10 text-red-400";
  if (diff > -20) return "bg-red-500/20 text-red-400";
  return "bg-red-500/30 text-red-300";
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
  const baseValue = baseCell?.value ?? data[Math.floor(data.length / 2)]?.value ?? 0;

  const cellMap = new Map<string, SensitivityCell>();
  data.forEach((cell) => cellMap.set(`${cell.row}-${cell.col}`, cell));

  return (
    <div className="rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">敏感性分析</h3>
        <p className="text-xs text-[var(--iris-text-muted)]">
          {rowLabel} vs {colLabel}
        </p>
      </div>
      <div className="overflow-x-auto p-3">
        <table className="w-full">
          <thead>
            <tr>
              <th className="px-2 py-1.5 text-left text-xs font-medium text-[var(--iris-text-muted)]">
                {rowLabel} \ {colLabel}
              </th>
              {colValues.map((col) => (
                <th
                  key={col}
                  className="px-2 py-1.5 text-center font-mono text-xs font-medium text-[var(--iris-text-muted)]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowValues.map((row) => (
              <tr key={row}>
                <td className="px-2 py-1.5 font-mono text-xs font-medium text-[var(--iris-text-muted)]">
                  {row}
                </td>
                {colValues.map((col) => {
                  const cell = cellMap.get(`${row}-${col}`);
                  const value = cell?.value ?? 0;
                  const isBase = cell?.isBase ?? false;
                  return (
                    <td
                      key={col}
                      className={`heatmap-cell px-2 py-1.5 text-center font-mono text-xs ${
                        isBase
                          ? "ring-2 ring-[var(--iris-accent)] font-bold text-[var(--iris-text)]"
                          : getCellColor(value, baseValue)
                      }`}
                    >
                      ${value.toFixed(0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
