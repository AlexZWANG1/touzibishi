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
    <div
      className="border border-[var(--iris-border)] px-[6px] py-[3px]"
      style={{ background: "rgba(7,8,12,0.95)" }}
    >
      <p
        className={`font-mono text-[11px] font-semibold ${
          point.isTarget
            ? "text-[var(--iris-accent)]"
            : "text-[var(--iris-data)]"
        }`}
      >
        {point.ticker}
        {point.isTarget && (
          <span className="ml-1 text-[10px] font-normal text-[var(--iris-text-muted)]">
            (target)
          </span>
        )}
      </p>
      <div className="flex gap-2 font-mono text-[10px] text-[var(--iris-text-secondary)]">
        <span>
          x: {point.x.toFixed(1)}
        </span>
        <span>
          y: {point.y.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export function CompsScatter({ data, xLabel, yLabel }: CompsScatterProps) {
  if (data.length === 0) return null;

  return (
    <div className="border border-[var(--iris-border)] overflow-hidden" role="figure" aria-label={`Valuation scatter chart: ${xLabel} vs ${yLabel}`}>
      <div className="p-[5px_8px] border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <span className="font-mono text-[11px] text-[var(--iris-accent)] uppercase tracking-[0.08em]">
          Valuation Scatter
        </span>
      </div>
      <div className="p-[4px]" style={{ background: "var(--iris-bg)" }}>
        <ResponsiveContainer width="100%" height={260}>
          <ScatterChart margin={{ top: 6, right: 10, bottom: 28, left: 16 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--iris-border)"
              opacity={0.3}
            />
            <XAxis
              type="number"
              dataKey="x"
              tick={{ fill: "#525264", fontSize: 10, fontFamily: "ui-monospace, monospace" }}
              stroke="var(--iris-border)"
              tickLine={{ stroke: "var(--iris-border)" }}
            >
              <Label
                value={xLabel}
                position="bottom"
                offset={8}
                style={{
                  fill: "#8B8B9E",
                  fontSize: 10,
                  fontFamily: "ui-monospace, monospace",
                }}
              />
            </XAxis>
            <YAxis
              type="number"
              dataKey="y"
              tick={{ fill: "#525264", fontSize: 10, fontFamily: "ui-monospace, monospace" }}
              stroke="var(--iris-border)"
              tickLine={{ stroke: "var(--iris-border)" }}
            >
              <Label
                value={yLabel}
                angle={-90}
                position="insideLeft"
                offset={-6}
                style={{
                  fill: "#8B8B9E",
                  fontSize: 10,
                  fontFamily: "ui-monospace, monospace",
                }}
              />
            </YAxis>
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ strokeDasharray: "3 3", stroke: "var(--iris-border)" }}
            />
            <Scatter data={data}>
              {data.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.isTarget ? "#F58025" : "#2DD4BF"}
                  r={entry.isTarget ? 7 : 4}
                  stroke={entry.isTarget ? "#F58025" : "transparent"}
                  strokeWidth={entry.isTarget ? 2 : 0}
                  opacity={entry.isTarget ? 1 : 0.75}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
