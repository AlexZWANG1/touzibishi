"use client";

interface CalibrationSummaryProps {
  hits: number;
  misses: number;
  recentRecalls: { company: string; date: string; relevance: number }[];
}

export function CalibrationSummary({ hits, misses, recentRecalls }: CalibrationSummaryProps) {
  const total = hits + misses;
  const accuracy = total > 0 ? (hits / total) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "命中", value: hits, color: "var(--green)" },
          { label: "未中", value: misses, color: "var(--red)" },
          { label: "准确率", value: `${accuracy.toFixed(0)}%`, color: "var(--cy-t)" },
        ].map((item) => (
          <div key={item.label} className="rounded-lg bg-[var(--bg)] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
              {item.label}
            </div>
            <div className="mt-2 font-mono text-[22px] font-semibold" style={{ color: item.color }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {recentRecalls.length > 0 && (
        <div className="rounded-lg bg-[var(--bg)] p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
            Recent Recalls
          </div>
          <div className="mt-3 space-y-2">
            {recentRecalls.map((recall, index) => (
              <div key={`${recall.company}-${index}`} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-[var(--t1)]">{recall.company}</div>
                  <div className="font-mono text-[11px] text-[var(--t4)]">{recall.date}</div>
                </div>
                <div className="font-mono text-[12px] text-[var(--cy-t)]">
                  {(recall.relevance * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
