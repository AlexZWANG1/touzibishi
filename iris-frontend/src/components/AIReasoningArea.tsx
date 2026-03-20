"use client";

import { useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { CalibrationSummary } from "./CalibrationSummary";

/** Strip all <thinking>...</thinking> blocks from text */
function stripThinking(text: string): string {
  return text.replace(/<thinking>[\s\S]*?<\/thinking>/g, "").trim();
}

export function ReportPanel() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const memoryPanel = useAnalysisStore((s) => s.memoryPanel);
  const scrollRef = useRef<HTMLDivElement>(null);

  const cleanText = useMemo(() => stripThinking(reasoningText), [reasoningText]);

  const hasMemory =
    memoryPanel.calibrationHits > 0 ||
    memoryPanel.calibrationMisses > 0 ||
    memoryPanel.recentRecalls.length > 0;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [cleanText]);

  if (!cleanText) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="font-mono text-[12px] text-[var(--iris-text-muted)]">
          等待分析报告...
        </p>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="min-h-0 flex-1 overflow-y-auto"
      style={{ padding: "16px 20px" }}
    >
      {/* Report content */}
      <div className="prose-iris">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {cleanText}
        </ReactMarkdown>
      </div>

      {/* Memory section at bottom of report */}
      {hasMemory && (
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
          <CalibrationSummary
            hits={memoryPanel.calibrationHits}
            misses={memoryPanel.calibrationMisses}
            recentRecalls={memoryPanel.recentRecalls}
          />
        </div>
      )}
    </div>
  );
}
