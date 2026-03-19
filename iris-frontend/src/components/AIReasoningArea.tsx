"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function AIReasoningArea() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const thinkingText = useAnalysisStore((s) => s.thinkingText);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Always show reasoning text only
  const activeText = reasoningText;

  // Auto-scroll to bottom when expanded and new content arrives
  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeText, expanded]);

  if (!reasoningText && !thinkingText) return null;

  const lines = activeText.split("\n");
  const lineCount = lines.length;
  // For preview, take last 2 non-empty lines as plain text
  const previewLines = lines.filter((l) => l.trim()).slice(-2).join(" · ");

  return (
    <div
      className="relative flex shrink-0 flex-col"
      style={{
        borderTop: "1px solid var(--iris-border)",
        maxHeight: "30%",
      }}
    >
      {/* Header / Toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1 border-none bg-transparent text-left"
        style={{ padding: "6px 10px" }}
      >
        {/* Muted chevron */}
        <svg
          className="flex-shrink-0"
          style={{
            width: 8,
            height: 8,
            color: "var(--iris-text-muted)",
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 150ms",
          }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 5l7 7-7 7"
          />
        </svg>

        <span
          className="font-mono"
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: "var(--iris-text-secondary)",
            letterSpacing: "0.06em",
            textTransform: "uppercase" as const,
          }}
        >
          分析笔记
        </span>

        {/* Line count */}
        <span
          style={{
            fontSize: 8,
            color: "var(--iris-text-muted)",
            fontWeight: 400,
          }}
        >
          {lineCount}行
        </span>
      </button>

      {/* Content area */}
      <div
        className="overflow-hidden"
        style={{
          maxHeight: expanded ? "calc(30vh - 30px)" : 0,
          transition: "max-height 200ms ease-in-out",
        }}
      >
        <div
          ref={scrollRef}
          className={expanded ? "overflow-y-auto" : "overflow-hidden"}
          style={{
            padding: "0 10px 6px 10px",
            maxHeight: expanded ? "calc(30vh - 30px)" : 0,
          }}
        >
          {expanded ? (
            <div className="prose-iris prose-iris-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {activeText}
              </ReactMarkdown>
            </div>
          ) : null}
        </div>
      </div>

      {/* Collapsed preview */}
      {!expanded && previewLines && (
        <p
          className="truncate font-mono"
          style={{
            fontSize: 9,
            lineHeight: 1.5,
            color: "var(--iris-text-secondary)",
            margin: 0,
            padding: "0 10px 4px 10px",
            maxHeight: 60,
            overflow: "hidden",
          }}
        >
          {previewLines}
        </p>
      )}
    </div>
  );
}
