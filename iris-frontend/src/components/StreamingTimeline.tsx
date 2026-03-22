"use client";

import { useEffect, useMemo, useRef } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { TimelineItem } from "./TimelineItem";
import type { TimelineEvent } from "@/types/analysis";
import { getKnownToolNames } from "@/utils/toolRegistry";

function interleaveThinking(toolEvents: TimelineEvent[], rawTextBuffer: string): TimelineEvent[] {
  if (!rawTextBuffer) return toolEvents;
  if (toolEvents.some((e) => e.tool === "thinking")) return toolEvents;

  const blocks: string[] = [];
  const re = /<thinking>([\s\S]*?)<\/thinking>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(rawTextBuffer)) !== null) {
    const text = m[1].trim();
    if (text) blocks.push(text);
  }
  if (blocks.length === 0) return toolEvents;

  const merged: TimelineEvent[] = [];
  let bi = 0; // block index

  for (let i = 0; i < toolEvents.length; i++) {
    // Insert a thinking block before a tool event when:
    // - we have blocks left, AND
    // - it's the first event, or a different tool from the previous one (new step)
    if (bi < blocks.length && (i === 0 || toolEvents[i].tool !== toolEvents[i - 1].tool)) {
      merged.push({
        id: `thinking-${bi}`,
        timestamp: toolEvents[i].timestamp - 0.001,
        tool: "thinking",
        message: blocks[bi].split("\n")[0]?.slice(0, 120) || "",
        phase: toolEvents[i].phase,
        color: "gold" as const,
        status: "complete" as const,
        fullText: blocks[bi],
      });
      bi++;
    }
    merged.push(toolEvents[i]);
  }

  // Remaining blocks go at the end
  const lastTs = toolEvents.length > 0 ? toolEvents[toolEvents.length - 1].timestamp : Date.now();
  while (bi < blocks.length) {
    merged.push({
      id: `thinking-${bi}`,
      timestamp: lastTs + 0.001 * bi,
      tool: "thinking",
      message: blocks[bi].split("\n")[0]?.slice(0, 120) || "",
      phase: "finalize" as const,
      color: "gold" as const,
      status: "complete" as const,
      fullText: blocks[bi],
    });
    bi++;
  }

  return merged;
}

export function StreamingTimeline() {
  const timeline = useAnalysisStore((s) => s.timeline);
  const rawTextBuffer = useAnalysisStore((s) => s._rawTextBuffer);
  const pageState = useAnalysisStore((s) => s.pageState);
  const bottomRef = useRef<HTMLDivElement>(null);

  const enrichedTimeline = useMemo(
    () => interleaveThinking(timeline, rawTextBuffer),
    [rawTextBuffer, timeline],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [enrichedTimeline.length]);

  if (enrichedTimeline.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 py-10 text-center text-[13px] text-[var(--t3)]">
        {pageState === "COMPLETE" ? "本轮分析没有记录工具调用。" : "Prism 正在准备工具链路..."}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto py-2">
      {enrichedTimeline.map((event, index) => (
        <TimelineItem key={event.id} event={event} isLast={index === enrichedTimeline.length - 1} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
