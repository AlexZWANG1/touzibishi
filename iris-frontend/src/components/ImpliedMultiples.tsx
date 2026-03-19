"use client";

interface ImpliedMultiplesProps {
  multiples: { label: string; value: string | number }[];
}

export function ImpliedMultiples({ multiples }: ImpliedMultiplesProps) {
  if (multiples.length === 0) return null;

  return (
    <div className="flex gap-[6px] mt-2 flex-wrap">
      {multiples.map((item, idx) => (
        <span
          key={idx}
          className="bg-[rgba(45,212,191,0.1)] text-[var(--iris-data)] px-[6px] py-[2px] font-mono text-[10px] font-semibold"
        >
          {item.label}:{" "}
          {typeof item.value === "number"
            ? item.value.toFixed(1) + "x"
            : item.value}
        </span>
      ))}
    </div>
  );
}
