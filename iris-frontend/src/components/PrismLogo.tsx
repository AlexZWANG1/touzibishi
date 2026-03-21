import { useId } from "react";
import { classNames } from "@/utils/formatters";

interface PrismLogoProps {
  size?: number;
  showWordmark?: boolean;
  className?: string;
  iconClassName?: string;
  textClassName?: string;
}

export function PrismLogo({
  size = 24,
  showWordmark = true,
  className,
  iconClassName,
  textClassName,
}: PrismLogoProps) {
  const fillId = useId();
  const lineId = useId();

  return (
    <span className={classNames("inline-flex items-center gap-[10px]", className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        className={iconClassName}
        aria-hidden="true"
      >
        <path
          d="M16 2L28 28H4L16 2Z"
          fill="none"
          stroke="var(--ac)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path d="M16 10L22 24H10L16 10Z" fill={`url(#${fillId})`} opacity="0.16" />
        <line
          x1="16"
          y1="2"
          x2="28"
          y2="28"
          stroke={`url(#${lineId})`}
          strokeWidth="1.6"
          opacity="0.65"
        />
        <defs>
          <linearGradient id={fillId} x1="10" y1="10" x2="22" y2="24">
            <stop stopColor="#6366F1" />
            <stop offset="0.55" stopColor="#06B6D4" />
            <stop offset="1" stopColor="#10B981" />
          </linearGradient>
          <linearGradient id={lineId} x1="16" y1="2" x2="28" y2="28">
            <stop stopColor="#6366F1" />
            <stop offset="0.55" stopColor="#06B6D4" />
            <stop offset="1" stopColor="#10B981" />
          </linearGradient>
        </defs>
      </svg>

      {showWordmark && (
        <span
          className={classNames(
            "font-sans text-[18px] font-bold tracking-[-0.03em] text-[var(--ink)]",
            textClassName,
          )}
        >
          Pr<span className="text-[var(--ac)]">i</span>sm
        </span>
      )}
    </span>
  );
}
