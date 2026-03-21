"use client";

import { useEffect, useMemo, useRef } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { TimelineItem } from "./TimelineItem";
import type { TimelineEvent } from "@/types/analysis";

const KNOWN_TOOLS = [
  "recall",
  "remember",
  "search_knowledge",
  "financials",
  "macro",
  "quote",
  "history",
  "valuation",
  "exa_search",
  "web_fetch",
  "create_hypothesis",
  "add_evidence_card",
  "generate_trade_signal",
  "get_portfolio",
];

function extractToolHint(thinkingText: string): string | null {
  let lastTool: string | null = null;
  for (const tool of KNOWN_TOOLS) {
    if (thinkingText.includes(tool)) {
      lastTool = tool;
    }
  }
  return lastTool;
}

function interleaveThinking(toolEvents: TimelineEvent[], rawTextBuffer: string): TimelineEvent[] {
  if (!rawTextBuffer) return toolEvents;
  if (toolEvents.some((event) => event.tool === "thinking")) return toolEvents;

  const thinkingBlocks: { text: string; toolHint: string | null }[] = [];
  const matcher = /<thinking>([\s\S]*?)<\/thinking>/g;
  let match: RegExpExecArray | null;

  while ((match = matcher.exec(rawTextBuffer)) !== null) {
    const text = match[1].trim();
    thinkingBlocks.push({ text, toolHint: extractToolHint(text) });
  }

  if (thinkingBlocks.length === 0) return toolEvents;

  const merged: TimelineEvent[] = [];
  const used = new Set<number>();
  let thinkingIndex = 0;

  for (let index = 0; index < toolEvents.length; index += 1) {
    const event = toolEvents[index];
    const block = thinkingBlocks[thinkingIndex];

    if (block && !used.has(thinkingIndex)) {
      const shouldPlace =
        (block.toolHint && event.tool.includes(block.toolHint.split("_")[0])) ||
        block.toolHint === event.tool ||
        (index === 0 && thinkingIndex === 0) ||
        (index > 0 && toolEvents[index - 1].tool !== event.tool);

      if (shouldPlace) {
        merged.push({
          id: `thinking-${thinkingIndex}`,
          timestamp: event.timestamp - 0.001,
          tool: "thinking",
          message: block.text.split("\n")[0]?.slice(0, 90) || "",
          phase: event.phase,
          color: "gold",
          status: "complete",
          fullText: block.text,
        });
        used.add(thinkingIndex);
        thinkingIndex += 1;
      }
    }

    merged.push(event);
  }

  for (let index = 0; index < thinkingBlocks.length; index += 1) {
    if (used.has(index)) continue;
    const block = thinkingBlocks[index];
    const lastTimestamp = toolEvents.length > 0 ? toolEvents[toolEvents.length - 1].timestamp : Date.now();
    merged.push({
      id: `thinking-${index}`,
      timestamp: lastTimestamp + 0.001 * index,
      tool: "thinking",
      message: block.text.split("\n")[0]?.slice(0, 90) || "",
      phase: "finalize",
      color: "gold",
      status: "complete",
      fullText: block.text,
    });
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
