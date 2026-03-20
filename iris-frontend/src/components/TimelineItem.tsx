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
  recall: "检索记忆",
  search_knowledge: "检索知识库",
  remember: "写入记忆",
  financials: "拉取财报",
  macro: "宏观数据",
  quote: "获取报价",
  history: "历史行情",
  valuation: "统一估值",
  get_portfolio: "查看持仓",
  generate_trade_signal: "交易信号",
  create_hypothesis: "形成假设",
  add_evidence_card: "添加证据",
  exa_search: "搜索资讯",
  web_fetch: "抓取网页",

  // Legacy tool name aliases (for replay compatibility)
  recall_memory: "回忆历史",
  fmp_get_financials: "拉取财报",
  yf_quote: "获取报价",
  yf_history: "历史行情",
  build_dcf: "构建DCF",
  get_comps: "可比分析",
  extract_observation: "提取观察",
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

  // User continuation message — render as a turn separator
  if (event.tool === "user_continue" || event.tool === "user_steering") {
    return (
      <div
        style={{
          padding: "6px 0",
          marginTop: 4,
          marginBottom: 4,
          borderTop: event.tool === "user_continue" ? "1px solid var(--iris-border)" : "none",
        }}
      >
        <span
          className="font-mono"
          style={{ fontSize: 12, color: "var(--iris-accent)", fontWeight: 500 }}
        >
          &gt; {event.message}
        </span>
      </div>
    );
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
      className="relative flex items-start"
      style={{ gap: 7, paddingTop: 2.5, paddingBottom: 2.5 }}
    >
      {/* Dot */}
      <div className="relative z-10 flex-shrink-0" style={{ marginTop: 4 }}>
        {isError ? (
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "var(--iris-bearish)",
            }}
          />
        ) : isRunning ? (
          <div
            className="animate-pulse"
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: dotColor,
            }}
          />
        ) : (
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: dotColor,
            }}
          />
        )}
      </div>

      {/* Connector line */}
      {!isLast && (
        <div
          className="absolute"
          style={{
            left: 2,
            top: 9,
            bottom: -2.5,
            width: 1,
            background: "var(--iris-border)",
          }}
        />
      )}

      {/* Content */}
      <div className="flex min-w-0 flex-1 items-center gap-1">
        {/* Tool label in teal + raw name as secondary */}
        {toolLabel && (
          <span className="flex flex-shrink-0 items-center gap-1">
            <span
              className="font-mono"
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
                className="font-mono"
                style={{
                  fontSize: 10,
                  color: "var(--iris-text-muted)",
                  opacity: 0.7,
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
              fontSize: 10,
              color: "var(--iris-text-muted)",
              opacity: 0.7,
            }}
          >
            {formatDuration(event.duration)}
          </span>
        )}

        {/* Timestamp */}
        <span
          className="ml-auto flex-shrink-0 font-mono"
          style={{ fontSize: 10, color: "var(--iris-text-muted)", opacity: 0.7 }}
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
    <div
      className="cursor-pointer flex items-start"
      style={{
        paddingTop: 1,
        paddingBottom: 1,
        borderLeft: "2px solid var(--iris-accent-dim)",
        paddingLeft: 6,
        marginLeft: 2,
        background: expanded ? "var(--iris-accent-glow)" : "transparent",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <span
        className="flex-shrink-0"
        style={{
          fontSize: 10,
          color: "var(--iris-accent-dim)",
          transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 150ms",
          display: "inline-block",
          marginTop: 1,
          marginRight: 4,
        }}
      >
        ▶
      </span>
      <div className="min-w-0 flex-1">
        {!expanded ? (
          <span
            className="truncate block font-mono"
            style={{
              fontSize: 11,
              color: "var(--iris-text-muted)",
              lineHeight: 1.4,
            }}
          >
            {event.message}
          </span>
        ) : (
          <pre
            className="whitespace-pre-wrap font-mono"
            style={{
              fontSize: 12,
              lineHeight: 1.5,
              color: "var(--iris-text-secondary)",
              margin: 0,
            }}
          >
            {fullText}
          </pre>
        )}
      </div>
    </div>
  );
}
