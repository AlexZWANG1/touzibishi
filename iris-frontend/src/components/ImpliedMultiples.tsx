"use client";

interface ImpliedMultiplesProps {
  multiples: { label: string; value: string | number }[];
}

export function ImpliedMultiples({ multiples }: ImpliedMultiplesProps) {
  if (multiples.length === 0) return null;

  return (
    <div className="prism-panel p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
        Implied Multiples
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {multiples.map((item, index) => (
          <span
            key={`${item.label}-${index}`}
            className="rounded-pill border border-[rgba(15,118,110,0.08)] bg-[var(--cy-s)] px-3 py-2 font-mono text-[11px] font-medium text-[var(--cy-t)]"
          >
            {item.label}: {typeof item.value === "number" ? `${item.value.toFixed(1)}x` : item.value}
          </span>
        ))}
      </div>
    </div>
  );
}
