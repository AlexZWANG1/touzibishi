"use client";

import type { TimelineEvent } from "@/types/analysis";
import { formatTime, formatDuration } from "@/utils/formatters";

interface TimelineItemProps {
  event: TimelineEvent;
  isLast: boolean;
}

const colorMap: Record<string, string> = {
  green: "var(--event-search)",
  blue: "var(--event-analyze)",
  amber: "var(--event-model)",
  gray: "var(--event-system)",
  purple: "var(--event-user)",
};

export function TimelineItem({ event, isLast }: TimelineItemProps) {
  const dotColor = colorMap[event.color] || "var(--event-system)";

  return (
    <div className="relative flex gap-3 pb-4">
      {/* Connector line */}
      {!isLast && (
        <div
          className="absolute left-[7px] top-[20px] w-0.5"
          style={{
            bottom: 0,
            background: "var(--iris-border)",
          }}
        />
      )}

      {/* Dot */}
      <div className="relative z-10 mt-1.5 flex-shrink-0">
        <div
          className={`h-[14px] w-[14px] rounded-full border-2 ${
            event.status === "running" ? "pulse-dot" : ""
          }`}
          style={{
            borderColor: dotColor,
            background: event.status === "complete" ? dotColor : "var(--iris-bg)",
            boxShadow: event.status === "running" ? `0 0 8px ${dotColor}60` : "none",
          }}
        />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p
            className={`text-sm leading-snug ${
              event.status === "error"
                ? "text-red-400"
                : "text-[var(--iris-text)]"
            }`}
          >
            {event.message}
          </p>
          <div className="flex flex-shrink-0 items-center gap-2">
            {event.duration != null && (
              <span className="font-mono text-xs text-[var(--iris-text-muted)]">
                {formatDuration(event.duration)}
              </span>
            )}
            <span className="font-mono text-xs text-[var(--iris-text-muted)]">
              {formatTime(event.timestamp)}
            </span>
          </div>
        </div>
        {event.status === "running" && (
          <div className="mt-1.5 h-1 w-24 overflow-hidden rounded-full bg-[var(--iris-border)]">
            <div
              className="h-full animate-pulse rounded-full"
              style={{ background: dotColor, width: "60%" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
