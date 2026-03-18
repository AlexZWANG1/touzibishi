"use client";

import { useRef, useEffect } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { TimelineItem } from "./TimelineItem";

export function StreamingTimeline() {
  const timeline = useAnalysisStore((s) => s.timeline);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [timeline.length]);

  if (timeline.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--iris-accent)] border-t-transparent" />
        <p className="text-sm text-[var(--iris-text-muted)]">正在初始化分析...</p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {timeline.map((event, idx) => (
        <TimelineItem
          key={event.id}
          event={event}
          isLast={idx === timeline.length - 1}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
