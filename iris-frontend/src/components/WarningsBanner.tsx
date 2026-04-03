"use client";

interface WarningsBannerProps {
  warnings: string[];
}

export function WarningsBanner({ warnings }: WarningsBannerProps) {
  if (warnings.length === 0) return null;

  return (
    <div className="rounded-lg border border-[rgba(245,158,11,0.2)] bg-[rgba(245,158,11,0.05)] px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#B45309]">
        DCF Warnings
      </div>
      <ul className="mt-2 space-y-1">
        {warnings.map((w, i) => (
          <li key={i} className="text-[12px] leading-[1.6] text-[#92400E]">
            {w}
          </li>
        ))}
      </ul>
    </div>
  );
}
