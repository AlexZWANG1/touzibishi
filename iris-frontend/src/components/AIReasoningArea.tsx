"use client";

import { useRef, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";

/** Strip all <thinking>...</thinking> blocks from text (safety net) */
function stripThinking(text: string): string {
  return text.replace(/<thinking>[\s\S]*?<\/thinking>/g, "").trim();
}

/** Split text into alternating AI/user segments for chat-style rendering */
interface ChatSegment {
  role: "ai" | "user";
  content: string;
}

function splitIntoChatSegments(text: string): ChatSegment[] {
  if (!text) return [];

  // Split on the turn separator pattern: ---\n\n**> message**\n\n
  // The user message pattern is: **> some text**
  const parts = text.split(/\n*---\n*/);
  const segments: ChatSegment[] = [];

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Check if this part is a user message: starts with **> and ends with **
    const userMatch = trimmed.match(/^\*\*>\s*([\s\S]*?)\*\*$/);
    if (userMatch) {
      segments.push({ role: "user", content: userMatch[1].trim() });
    } else {
      segments.push({ role: "ai", content: trimmed });
    }
  }

  return segments;
}

/** Collapsible thinking block with distinct visual treatment */
function ThinkingBlock({ text, isStreaming }: { text: string; isStreaming: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  // Auto-scroll the thinking content during streaming
  useEffect(() => {
    if (expanded && isStreaming && preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [text, expanded, isStreaming]);

  if (!text) return null;

  const firstLine = text.split("\n")[0]?.slice(0, 80) || "";

  return (
    <div
      style={{
        marginBottom: 12,
        borderRadius: 6,
        border: "1px solid rgba(245,128,37,0.12)",
        background: "rgba(245,128,37,0.03)",
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="font-mono"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          width: "100%",
          padding: "6px 10px",
          border: "none",
          background: "none",
          cursor: "pointer",
          fontSize: 11,
          color: "var(--iris-accent-dim)",
          fontWeight: 500,
          textAlign: "left",
        }}
      >
        <span
          style={{
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 150ms",
            display: "inline-block",
            fontSize: 8,
            flexShrink: 0,
          }}
        >
          &#9654;
        </span>
        <span style={{ opacity: 0.7 }}>
          {expanded ? "思考过程" : firstLine || "思考过程"}
        </span>
        {isStreaming && (
          <span
            className="animate-pulse"
            style={{ fontSize: 8, marginLeft: "auto", flexShrink: 0 }}
          >
            &#9679;
          </span>
        )}
      </button>
      {expanded && (
        <pre
          ref={preRef}
          className="font-mono"
          style={{
            padding: "4px 10px 8px",
            margin: 0,
            fontSize: 11,
            lineHeight: 1.5,
            color: "var(--iris-text-muted)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            maxHeight: 240,
            overflowY: "auto",
          }}
        >
          {text}
        </pre>
      )}
    </div>
  );
}

export function ReportPanel() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const thinkingText = useAnalysisStore((s) => s.thinkingText);
  const pageState = useAnalysisStore((s) => s.pageState);
  const memoryPanel = useAnalysisStore((s) => s.memoryPanel);
  const scrollRef = useRef<HTMLDivElement>(null);

  const cleanText = useMemo(() => stripThinking(reasoningText), [reasoningText]);

  const segments = useMemo(() => splitIntoChatSegments(cleanText), [cleanText]);

  const isStreaming = pageState === "RUNNING";

  const hasMemory =
    memoryPanel.calibrationHits > 0 ||
    memoryPanel.calibrationMisses > 0 ||
    memoryPanel.recentRecalls.length > 0;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [cleanText]);

  if (!cleanText && !thinkingText) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="font-mono text-[12px] text-[var(--iris-text-muted)]">
          {isStreaming ? "思考中..." : "等待回复..."}
        </p>
      </div>
    );
  }

  const hasMultipleTurns = segments.length > 1;

  return (
    <div
      ref={scrollRef}
      className="min-h-0 flex-1 overflow-y-auto"
      style={{ padding: "16px 20px" }}
    >
      {/* Thinking block — collapsible, distinct styling */}
      {thinkingText && (
        <ThinkingBlock text={thinkingText} isStreaming={isStreaming} />
      )}

      {/* Chat content */}
      <div className="flex flex-col gap-4">
        {hasMultipleTurns ? (
          segments.map((seg, i) =>
            seg.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div
                  className="font-mono"
                  style={{
                    maxWidth: "80%",
                    padding: "8px 12px",
                    borderRadius: "8px 8px 2px 8px",
                    background: "rgba(245,128,37,0.12)",
                    border: "1px solid rgba(245,128,37,0.25)",
                    color: "var(--iris-accent)",
                    fontSize: 13,
                    fontWeight: 500,
                    lineHeight: 1.5,
                  }}
                >
                  {seg.content}
                </div>
              </div>
            ) : (
              <div key={i} className="prose-iris">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {seg.content}
                </ReactMarkdown>
              </div>
            )
          )
        ) : cleanText ? (
          <div className="prose-iris">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanText}
            </ReactMarkdown>
          </div>
        ) : null}
      </div>

      {/* Memory / calibration section at bottom */}
      <div
        style={{
          marginTop: 24,
          paddingTop: 12,
          borderTop: "1px solid var(--iris-border)",
        }}
      >
        <h3
          className="font-mono"
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--iris-accent)",
            letterSpacing: "0.08em",
            textTransform: "uppercase" as const,
            marginBottom: 8,
          }}
        >
          记忆 / 校准
        </h3>
        {hasMemory ? (
          <CalibrationSummary
            hits={memoryPanel.calibrationHits}
            misses={memoryPanel.calibrationMisses}
            recentRecalls={memoryPanel.recentRecalls}
          />
        ) : (
          <p className="font-mono text-[12px] text-[var(--iris-text-muted)]">
            暂无校准记录 — 分析更多公司后将积累预测准确度数据
          </p>
        )}
      </div>
    </div>
  );
}
