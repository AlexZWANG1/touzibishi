"use client";

import { useState } from "react";
import type { TimelineEvent } from "@/types/analysis";
import { formatTime, formatDuration } from "@/utils/formatters";

interface TimelineItemProps {
  event: TimelineEvent;
  isLast: boolean;
}

const phaseColorMap: Record<string, string> = {
  gather: "var(--iris-phase-gather)",
  analyze: "var(--iris-phase-analyze)",
  evaluate: "var(--iris-phase-evaluate)",
  finalize: "var(--iris-phase-finalize)",
};

const TOOL_LABELS: Record<string, string> = {
  recall_memory: "回忆历史",
  fmp_get_financials: "拉取财报",
  yf_quote: "获取报价",
  yf_history: "历史行情",
  build_dcf: "构建DCF",
  get_comps: "可比分析",
  exa_search: "搜索资讯",
  web_fetch: "抓取网页",
  extract_observation: "提取观察",
  create_hypothesis: "形成假设",
  add_evidence_card: "添加证据",
  save_memory: "保存记忆",
  memory_search: "搜索记忆",
  query_knowledge: "查询知识",
  check_calibration: "校准检查",
  fred_get_macro: "宏观数据",
};

export function TimelineItem({ event, isLast }: TimelineItemProps) {
  if (event.tool === "thinking") {
    return <ThinkingItem event={event} />;
  }

  const dotColor = phaseColorMap[event.phase] || "var(--iris-text-muted)";
  const isRunning = event.status === "running";
  const isError = event.status === "error";

  const toolLabel =
    event.tool && event.tool !== "system" && event.tool !== "analysis_complete"
      ? TOOL_LABELS[event.tool] || event.tool
      : null;
  const showRawName =
    toolLabel && TOOL_LABELS[event.tool!] ? event.tool : null;

  return (
    <div
      className="group relative flex items-start gap-2 px-1"
      style={{ minHeight: 24, paddingTop: 2, paddingBottom: 2 }}
    >
      {/* Dot on the connector line - 6px */}
      <div className="relative z-10 flex w-[11px] flex-shrink-0 items-center justify-center" style={{ marginTop: 5 }}>
        {isError ? (
          <div
            className="rounded-full"
            style={{
              width: 6,
              height: 6,
              background: "var(--iris-bearish)",
            }}
          />
        ) : isRunning ? (
          <div className="relative flex items-center justify-center">
            <div
              className="absolute animate-ping rounded-full opacity-25"
              style={{ width: 10, height: 10, background: dotColor }}
            />
            <div
              className="rounded-full"
              style={{ width: 6, height: 6, background: dotColor }}
            />
          </div>
        ) : (
          <div
            className="rounded-full"
            style={{ width: 6, height: 6, background: dotColor }}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex min-w-0 flex-1 items-center gap-1.5" style={{ paddingTop: 1, paddingBottom: 1 }}>
        {/* Tool label in teal + raw name as secondary */}
        {toolLabel && (
          <span className="flex flex-shrink-0 items-center gap-1">
            <span
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: "var(--iris-data)",
              }}
            >
              {toolLabel}
            </span>
            {showRawName && (
              <span
                style={{
                  fontSize: 9,
                  color: "var(--iris-text-muted)",
                  opacity: 0.6,
                }}
              >
                {showRawName}
              </span>
            )}
          </span>
        )}

        {/* Message text */}
        <span
          className="min-w-0 flex-1 truncate"
          style={{
            fontSize: 11,
            color: isError
              ? "var(--iris-bearish)"
              : "var(--iris-text-secondary)",
          }}
        >
          {event.message}
        </span>

        {/* Duration badge */}
        {event.duration != null && (
          <span
            className="flex-shrink-0 font-mono"
            style={{
              fontSize: 9,
              color: "var(--iris-text-muted)",
            }}
          >
            {formatDuration(event.duration)}
          </span>
        )}

        {/* Timestamp */}
        <span
          className="flex-shrink-0 font-mono"
          style={{ fontSize: 9, color: "var(--iris-text-muted)", opacity: 0.7 }}
        >
          {formatTime(event.timestamp)}
        </span>
      </div>
    </div>
  );
}

function ThinkingItem({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const fullText = event.fullText || event.message;

  return (
    <div className="relative px-1" style={{ paddingTop: 2, paddingBottom: 2 }}>
      <div
        className="cursor-pointer rounded-[2px] px-2 py-1"
        style={{
          borderLeft: "2px solid var(--iris-accent)",
          background: expanded ? "rgba(201,168,76,0.05)" : "transparent",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-1.5">
          <span
            style={{
              fontSize: 9,
              color: "var(--iris-accent)",
              transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
              transition: "transform 150ms",
              display: "inline-block",
            }}
          >
            ▶
          </span>
          <span
            style={{
              fontSize: 10,
              color: "var(--iris-accent)",
              fontWeight: 600,
            }}
          >
            AI 思考
          </span>
          {!expanded && (
            <span
              className="truncate"
              style={{
                fontSize: 10,
                color: "var(--iris-text-muted)",
              }}
            >
              — {event.message}
            </span>
          )}
        </div>
        {expanded && (
          <pre
            className="mt-1 whitespace-pre-wrap font-mono"
            style={{
              fontSize: 10,
              lineHeight: 1.5,
              color: "var(--iris-text-secondary)",
            }}
          >
            {fullText}
          </pre>
        )}
      </div>
    </div>
  );
}
