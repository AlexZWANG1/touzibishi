"use client";

import { useRef, useEffect, useMemo } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { TimelineItem } from "./TimelineItem";
import type { TimelineEvent } from "@/types/analysis";

/**
 * Extract tool name hints from a thinking block text.
 * Looks for patterns like `recall`, `valuation`, etc.
 */
const KNOWN_TOOLS = [
  "recall", "remember", "search_knowledge",
  "financials", "macro", "quote", "history",
  "valuation",
  "exa_search", "web_fetch",
  "create_hypothesis", "add_evidence_card",
  "generate_trade_signal", "get_portfolio",
];

function extractToolHint(thinkingText: string): string | null {
  // Look for tool mentions — the LAST tool mentioned is usually the one about to be called
  let lastTool: string | null = null;
  for (const tool of KNOWN_TOOLS) {
    if (thinkingText.includes(tool)) {
      lastTool = tool;
    }
  }
  return lastTool;
}

/**
 * Interleave thinking blocks with tool call events.
 * Each thinking block is placed before the first tool call it mentions.
 */
function interleaveThinking(
  toolEvents: TimelineEvent[],
  rawTextBuffer: string
): TimelineEvent[] {
  if (!rawTextBuffer) return toolEvents;
  // Replay snapshots already include parsed thinking entries from backend.
  // Only synthesize client-side thinking entries for live runs.
  if (toolEvents.some((ev) => ev.tool === "thinking")) return toolEvents;

  // Extract all thinking blocks
  const thinkingBlocks: { text: string; toolHint: string | null }[] = [];
  const re = /<thinking>([\s\S]*?)<\/thinking>/g;
  let match;
  while ((match = re.exec(rawTextBuffer)) !== null) {
    const text = match[1].trim();
    thinkingBlocks.push({ text, toolHint: extractToolHint(text) });
  }

  if (thinkingBlocks.length === 0) return toolEvents;

  const result: TimelineEvent[] = [];
  let thinkIdx = 0;

  // Track which tool events we've seen to match thinking blocks
  // Strategy: for each tool event, check if the next unplaced thinking block
  // mentions this tool (or a related tool). If so, insert it before.
  const usedThinking = new Set<number>();

  for (let i = 0; i < toolEvents.length; i++) {
    const ev = toolEvents[i];

    // Try to place the next unplaced thinking block before this tool
    if (thinkIdx < thinkingBlocks.length && !usedThinking.has(thinkIdx)) {
      const tb = thinkingBlocks[thinkIdx];
      const toolName = ev.tool;

      // Place thinking if: it hints at this tool, OR it's the first tool and first thinking
      const shouldPlace =
        (tb.toolHint && toolName.includes(tb.toolHint.split("_")[0])) ||
        (tb.toolHint === toolName) ||
        (i === 0 && thinkIdx === 0) ||
        // If the previous tool was different from current, this might be a new "group"
        (i > 0 && toolEvents[i - 1].tool !== toolName && !usedThinking.has(thinkIdx));

      if (shouldPlace) {
        const block = tb.text;
        const firstLine = block.split("\n")[0]?.slice(0, 80) || "";
        result.push({
          id: `thinking-${thinkIdx}`,
          timestamp: ev.timestamp - 0.001,
          tool: "thinking",
          message: firstLine,
          phase: ev.phase,
          color: "gold",
          status: "complete",
          fullText: block,
        });
        usedThinking.add(thinkIdx);
        thinkIdx++;
      }
    }
    result.push(ev);
  }

  // Any remaining thinking blocks go at the end
  for (let t = 0; t < thinkingBlocks.length; t++) {
    if (usedThinking.has(t)) continue;
    const block = thinkingBlocks[t].text;
    const firstLine = block.split("\n")[0]?.slice(0, 80) || "";
    const lastTs = toolEvents.length > 0
      ? toolEvents[toolEvents.length - 1].timestamp
      : Date.now();
    result.push({
      id: `thinking-${t}`,
      timestamp: lastTs + 0.001 * t,
      tool: "thinking",
      message: firstLine,
      phase: "finalize",
      color: "gold",
      status: "complete",
      fullText: block,
    });
  }

  return result;
}

export function StreamingTimeline() {
  const timeline = useAnalysisStore((s) => s.timeline);
  const rawTextBuffer = useAnalysisStore((s) => s._rawTextBuffer);
  const pageState = useAnalysisStore((s) => s.pageState);
  const bottomRef = useRef<HTMLDivElement>(null);

  const enrichedTimeline = useMemo(
    () => interleaveThinking(timeline, rawTextBuffer),
    [timeline, rawTextBuffer]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [enrichedTimeline.length]);

  if (enrichedTimeline.length === 0) {
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
      {enrichedTimeline.map((event, idx) => (
        <TimelineItem
          key={event.id}
          event={event}
          isLast={idx === enrichedTimeline.length - 1}
        />
      ))}

      <div ref={bottomRef} />
    </div>
  );
}
