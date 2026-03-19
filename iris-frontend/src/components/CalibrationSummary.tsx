"use client";

interface CalibrationSummaryProps {
  hits: number;
  misses: number;
  recentRecalls: { company: string; date: string; relevance: number }[];
}

export function CalibrationSummary({
  hits,
  misses,
  recentRecalls,
}: CalibrationSummaryProps) {
  const total = hits + misses;
  const accuracy = total > 0 ? (hits / total) * 100 : 0;

  return (
    <div>
      {/* Inline stats row */}
      <div className="flex items-center gap-3 font-mono text-[11px]">
        <span className="text-[10px] text-[var(--iris-text-muted)] uppercase tracking-[0.06em]">命中</span>
        <span className="font-mono text-[13px] font-bold text-[#22C55E]">{hits}</span>
        <span className="text-[var(--iris-border)]">|</span>
        <span className="text-[10px] text-[var(--iris-text-muted)] uppercase tracking-[0.06em]">未中</span>
        <span className="font-mono text-[13px] font-bold text-[#EF4444]">{misses}</span>
        <span className="text-[var(--iris-border)]">|</span>
        <span className="text-[10px] text-[var(--iris-text-muted)] uppercase tracking-[0.06em]">准确率</span>
        <span className="font-mono text-[13px] font-bold text-[var(--iris-data)]">{accuracy.toFixed(0)}%</span>
      </div>

      {/* Recent recalls compact list */}
      {recentRecalls.length > 0 && (
        <div className="border-t border-[var(--iris-border)] mt-[6px] pt-[4px]">
          {recentRecalls.map((recall, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between py-[2px] font-mono text-[11px]"
            >
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--iris-text-muted)]">
                  {recall.date}
                </span>
                <span className="text-[var(--iris-text)]">
                  {recall.company}
                </span>
              </div>
              <span className="text-[var(--iris-data)]">
                {(recall.relevance * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
