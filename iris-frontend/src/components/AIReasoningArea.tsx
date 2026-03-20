"use client";

import { useRef, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";

/**
 * Aggressively strip any <thinking> tag artifacts from text (safety net).
 * Handles: complete blocks, unclosed blocks, partial tags, and leftover fragments.
 */
function stripThinking(text: string): string {
  let clean = text;
  // 1. Complete blocks: <thinking>...</thinking>
  clean = clean.replace(/<thinking>[\s\S]*?<\/thinking>/g, "");
  // 2. Unclosed block at end: <thinking>... (no closing tag)
  clean = clean.replace(/<thinking>[\s\S]*$/g, "");
  // 3. Orphaned closing tag or partial opening: inking>..., </thinking>, <thinking
  clean = clean.replace(/^[^<]*?(?:inking|hinking|thinking)>\s*/g, "");
  clean = clean.replace(/<\/thinking>/g, "");
  clean = clean.replace(/<thinking\s*$/g, "");
  return clean.trim();
}

/** Split text into alternating AI/user segments for chat-style rendering */
interface ChatSegment {
  role: "ai" | "user";
  content: string;
}

const TURN_SENTINEL = "<!---TURN--->";

function splitIntoChatSegments(text: string): ChatSegment[] {
  if (!text) return [];

  const parts = text.split(TURN_SENTINEL);
  const segments: ChatSegment[] = [];

  for (let i = 0; i < parts.length; i++) {
    const content = parts[i].trim();
    if (!content) continue;
    segments.push({
      role: i % 2 === 0 ? "ai" : "user",
      content,
    });
  }

  return segments;
}

/**
 * System Trace — collapsible thinking block.
 * Styled as dim internal reasoning, clearly distinct from conversation output.
 * Uses CSS grid trick for smooth height animation.
 */
function ThinkingBlock({ text, isStreaming }: { text: string; isStreaming: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  // Auto-expand during streaming so user sees the reasoning live
  useEffect(() => {
    if (isStreaming && text) setExpanded(true);
  }, [isStreaming, text]);

  // Auto-collapse when streaming ends
  useEffect(() => {
    if (!isStreaming && expanded) setExpanded(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]);

  // Auto-scroll content during streaming
  useEffect(() => {
    if (expanded && isStreaming && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [text, expanded, isStreaming]);

  if (!text) return null;

  const preview = text.split("\n")[0]?.slice(0, 60) || "";

  return (
    <div
      className={`iris-thinking-block ${isStreaming ? "iris-thinking-block--streaming" : ""}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="iris-thinking-toggle"
      >
        <span
          className={`iris-thinking-chevron ${expanded ? "iris-thinking-chevron--open" : ""}`}
        >
          &#9654;
        </span>
        <span className="iris-thinking-label">TRACE</span>
        {!expanded && (
          <span className="iris-thinking-preview">{preview}</span>
        )}
        {isStreaming && <span className="iris-thinking-dot" />}
      </button>

      <div className={`iris-thinking-body ${expanded ? "iris-thinking-body--open" : ""}`}>
        <div>
          <div ref={contentRef} className="iris-thinking-content">
            {text}
          </div>
        </div>
      </div>
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
