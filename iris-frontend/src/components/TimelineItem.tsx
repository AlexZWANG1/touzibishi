"use client";

import { memo, useState } from "react";
import type { TimelineEvent } from "@/types/analysis";
import { formatDuration, formatTime } from "@/utils/formatters";
import { getToolLabel } from "@/utils/toolRegistry";

interface TimelineItemProps {
  event: TimelineEvent;
  isLast: boolean;
}

const PHASE_COLOR_MAP: Record<string, string> = {
  gather: "var(--phase-gather)",
  analyze: "var(--phase-analyze)",
  evaluate: "var(--phase-evaluate)",
  finalize: "var(--phase-finalize)",
};


export const TimelineItem = memo(function TimelineItem({ event, isLast }: TimelineItemProps) {
  if (event.tool === "thinking") {
    return <ThinkingItem event={event} />;
  }

  if (event.tool === "user_continue" || event.tool === "user_steering") {
    return (
      <div className="rounded-lg bg-[var(--ac-s)] px-3 py-2 text-[12px] text-[var(--ac)]">
        <span className="mr-2 font-mono">&gt;</span>
        {event.message}
      </div>
    );
  }

  const dotColor =
    event.status === "error"
      ? "var(--red)"
      : PHASE_COLOR_MAP[event.phase] || "var(--t3)";
  const toolLabel = getToolLabel(event.tool);

  return (
    <div className="relative flex gap-3 px-4 py-3 animate-[slide-in-left_0.3s_cubic-bezier(0.16,1,0.3,1)]">
      <div className="relative z-10 mt-1.5 shrink-0">
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{
            background: dotColor,
            opacity: event.status === "running" ? 0.8 : 1,
          }}
        />
      </div>

      {!isLast && (
        <div
          className="absolute left-[20px] top-[28px] bottom-0 w-px"
          style={{ background: "var(--b1)" }}
        />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-medium text-[var(--cy-t)]">{toolLabel}</span>
              <span className="font-mono text-[10px] text-[var(--t4)]">{formatTime(event.timestamp)}</span>
            </div>
            <div
              className="mt-1 text-[12px] leading-[1.6]"
              style={{
                color: event.status === "error" ? "var(--red)" : "var(--t3)",
              }}
            >
              {event.message}
            </div>
          </div>

          {event.duration != null && (
            <span className="shrink-0 rounded-pill bg-[var(--bg-2)] px-2 py-1 font-mono text-[10px] text-[var(--t3)]">
              {formatDuration(event.duration)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
});

function ThinkingItem({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const fullText = event.fullText || event.message;

  return (
    <div className="px-4 py-2">
      <div className="overflow-hidden rounded-lg border border-[var(--ac-m)] bg-[var(--ac-s)]">
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="flex w-full items-center gap-3 px-3 py-2 text-left"
        >
          <span
            className="inline-block text-[9px] text-[var(--ac)] transition-transform"
            style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
          >
            ▶
          </span>
          <span className="text-[12px] font-medium text-[var(--ac)]">Trace</span>
          <span className="min-w-0 flex-1 truncate text-[11px] text-[var(--t3)]">{event.message}</span>
        </button>
        {expanded && (
          <pre className="overflow-x-auto border-t border-[var(--ac-m)] px-3 py-3 font-mono text-[11px] leading-[1.65] text-[var(--t2)]">
            {fullText}
          </pre>
        )}
      </div>
    </div>
  );
}
