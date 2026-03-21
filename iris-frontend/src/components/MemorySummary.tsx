"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function MemorySummary() {
  const { calibrationHits, calibrationMisses, recentRecalls } =
    useAnalysisStore((s) => s.memoryPanel);

  const hasCalibration = calibrationHits > 0 || calibrationMisses > 0;
  const hasRecalls = recentRecalls.length > 0;

  if (!hasCalibration && !hasRecalls) return null;

  const total = calibrationHits + calibrationMisses;
  const accuracy = total > 0 ? Math.round((calibrationHits / total) * 100) : 0;

  return (
    <div style={{ padding: "6px 10px" }}>
      <p
        className="font-mono"
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--t3)",
          letterSpacing: "0.08em",
          textTransform: "uppercase" as const,
          marginBottom: 4,
        }}
      >
        记忆
      </p>

      {hasCalibration && (
        <div className="flex items-center gap-3 font-mono" style={{ fontSize: 11 }}>
          <span style={{ color: "var(--green)" }}>{calibrationHits} 命中</span>
          <span style={{ color: "var(--red)" }}>{calibrationMisses} 偏差</span>
          <span style={{ color: "var(--t2)" }}>{accuracy}% 准确</span>
        </div>
      )}

      {hasRecalls && (
        <div style={{ marginTop: 4 }}>
          {recentRecalls.slice(0, 3).map((recall, i) => (
            <p
              key={i}
              className="truncate font-mono"
              style={{
                fontSize: 11,
                color: "var(--t2)",
                lineHeight: 1.6,
              }}
            >
              {recall.company} ({recall.date})
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
