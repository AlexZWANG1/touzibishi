"use client";

interface ImpliedMultiplesProps {
  multiples: { label: string; value: string | number }[];
}

export function ImpliedMultiples({ multiples }: ImpliedMultiplesProps) {
  if (multiples.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--iris-border)]">
      <div className="border-b border-[var(--iris-border)] bg-[var(--iris-surface)] px-4 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--iris-text)]">隐含倍数</h3>
      </div>
      <div className="grid grid-cols-2 gap-px bg-[var(--iris-border)]">
        {multiples.map((item, idx) => (
          <div key={idx} className="bg-[var(--iris-bg)] px-4 py-3">
            <p className="mb-0.5 text-xs text-[var(--iris-text-muted)]">{item.label}</p>
            <p className="font-mono text-base font-semibold text-[var(--iris-text)]">
              {typeof item.value === "number" ? item.value.toFixed(1) + "x" : item.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
