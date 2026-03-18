"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Label,
} from "recharts";
import type { ScatterPoint } from "@/types/analysis";

interface CompsScatterProps {
  data: ScatterPoint[];
  xLabel: string;
  yLabel: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: ScatterPoint;
  }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] px-3 py-2 shadow-lg">
      <p className="mb-1 font-medium text-[var(--iris-text)]">{point.ticker}</p>
      <p className="text-xs text-[var(--iris-text-secondary)]">
        x: {point.x.toFixed(1)} / y: {point.y.toFixed(1)}
      </p>
    </div>
  );
}

export function CompsScatter({ data, xLabel, yLabel }: CompsScatterProps) {
  if (data.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--iris-border)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--iris-text)]">
        估值散点图
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--iris-border)"
            opacity={0.5}
          />
          <XAxis
            type="number"
            dataKey="x"
            tick={{ fill: "var(--iris-text-muted)", fontSize: 11 }}
            stroke="var(--iris-border)"
          >
            <Label
              value={xLabel}
              position="bottom"
              offset={10}
              style={{ fill: "var(--iris-text-secondary)", fontSize: 12 }}
            />
          </XAxis>
          <YAxis
            type="number"
            dataKey="y"
            tick={{ fill: "var(--iris-text-muted)", fontSize: 11 }}
            stroke="var(--iris-border)"
          >
            <Label
              value={yLabel}
              angle={-90}
              position="insideLeft"
              offset={-5}
              style={{ fill: "var(--iris-text-secondary)", fontSize: 12 }}
            />
          </YAxis>
          <Tooltip content={<CustomTooltip />} />
          <Scatter data={data} fill="var(--iris-accent)">
            {data.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.isTarget ? "var(--phase-evaluate)" : "var(--iris-accent)"}
                r={entry.isTarget ? 8 : 5}
                stroke={entry.isTarget ? "var(--phase-evaluate)" : "none"}
                strokeWidth={entry.isTarget ? 2 : 0}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
