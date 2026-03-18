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
    <div className="space-y-4">
      {/* Accuracy summary */}
      <div className="rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--iris-text)]">
          校准表现
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-[var(--iris-text-muted)]">命中</p>
            <p className="font-mono text-xl font-bold text-[var(--status-bullish)]">
              {hits}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--iris-text-muted)]">未中</p>
            <p className="font-mono text-xl font-bold text-[var(--status-bearish)]">
              {misses}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--iris-text-muted)]">准确率</p>
            <p className="font-mono text-xl font-bold text-[var(--iris-text)]">
              {accuracy.toFixed(0)}%
            </p>
          </div>
        </div>
        {total > 0 && (
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--iris-border)]">
            <div
              className="h-full rounded-full bg-[var(--status-bullish)]"
              style={{ width: `${accuracy}%` }}
            />
          </div>
        )}
      </div>

      {/* Recent recalls */}
      {recentRecalls.length > 0 && (
        <div className="rounded-lg border border-[var(--iris-border)]">
          <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
            <h3 className="text-sm font-semibold text-[var(--iris-text)]">
              最近回忆
            </h3>
          </div>
          <div className="divide-y divide-[var(--iris-border)]">
            {recentRecalls.map((recall, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between px-4 py-2.5"
              >
                <div>
                  <span className="text-sm font-medium text-[var(--iris-text)]">
                    {recall.company}
                  </span>
                  <p className="text-xs text-[var(--iris-text-muted)]">
                    {recall.date}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="h-1.5 w-12 overflow-hidden rounded-full bg-[var(--iris-border)]"
                  >
                    <div
                      className="h-full rounded-full bg-[var(--iris-accent)]"
                      style={{ width: `${recall.relevance * 100}%` }}
                    />
                  </div>
                  <span className="font-mono text-xs text-[var(--iris-text-muted)]">
                    {(recall.relevance * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
