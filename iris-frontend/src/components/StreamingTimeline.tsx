"use client";

import { useRef, useEffect } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { TimelineItem } from "./TimelineItem";

export function StreamingTimeline() {
  const timeline = useAnalysisStore((s) => s.timeline);
  const pageState = useAnalysisStore((s) => s.pageState);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [timeline.length]);

  if (timeline.length === 0) {
    const isComplete = pageState === "COMPLETE";
    return (
      <div
        className="flex flex-1 items-center justify-center"
        style={{ padding: "6px 8px" }}
      >
        <p
          className="font-mono"
          style={{ fontSize: 12, color: "var(--iris-text-muted)" }}
        >
          {isComplete ? "无工具调用记录" : "正在初始化分析..."}
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-y-auto"
      style={{ padding: "6px 8px" }}
    >
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
