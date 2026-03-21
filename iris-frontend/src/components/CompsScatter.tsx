"use client";

import {
  CartesianGrid,
  Cell,
  Label,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScatterPoint } from "@/types/analysis";

interface CompsScatterProps {
  data: ScatterPoint[];
  xLabel: string;
  yLabel: string;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ScatterPoint }>;
}) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;

  return (
    <div className="rounded-lg border border-[var(--b1)] bg-white px-3 py-2 shadow-card">
      <div className="font-mono text-[12px] font-semibold text-[var(--ac)]">{point.ticker}</div>
      <div className="mt-1 flex gap-3 font-mono text-[11px] text-[var(--t3)]">
        <span>x: {point.x.toFixed(1)}</span>
        <span>y: {point.y.toFixed(1)}%</span>
      </div>
    </div>
  );
}

export function CompsScatter({ data, xLabel, yLabel }: CompsScatterProps) {
  if (data.length === 0) return null;

  return (
    <div className="prism-panel overflow-hidden">
      <div className="border-b border-[var(--b1)] px-5 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--t1)]">Valuation Scatter</h3>
      </div>
      <div className="p-4">
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 10, right: 16, bottom: 32, left: 12 }}>
            <CartesianGrid stroke="rgba(0,0,0,0.08)" strokeDasharray="4 4" />
            <XAxis
              type="number"
              dataKey="x"
              stroke="rgba(0,0,0,0.12)"
              tick={{ fill: "#888888", fontSize: 10, fontFamily: "var(--mono)" }}
            >
              <Label value={xLabel} position="bottom" offset={10} style={{ fill: "#888888", fontSize: 11 }} />
            </XAxis>
            <YAxis
              type="number"
              dataKey="y"
              stroke="rgba(0,0,0,0.12)"
              tick={{ fill: "#888888", fontSize: 10, fontFamily: "var(--mono)" }}
            >
              <Label
                value={yLabel}
                angle={-90}
                position="insideLeft"
                offset={-4}
                style={{ fill: "#888888", fontSize: 11 }}
              />
            </YAxis>
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "rgba(67,56,202,0.18)", strokeDasharray: "4 4" }} />
            <Scatter data={data}>
              {data.map((entry, index) => (
                <Cell
                  key={`${entry.ticker}-${index}`}
                  fill={entry.isTarget ? "#4338CA" : "#06B6D4"}
                  opacity={entry.isTarget ? 1 : 0.72}
                  stroke={entry.isTarget ? "#312E81" : "transparent"}
                  strokeWidth={entry.isTarget ? 2 : 0}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
