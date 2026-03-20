"use client";

import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function ReportPanel() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [reasoningText]);

  if (!reasoningText) {
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
      <div className="prose-iris">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {reasoningText}
        </ReactMarkdown>
      </div>
    </div>
  );
}
