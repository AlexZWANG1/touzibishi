"use client";

import { useState } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function AIReasoningArea() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const [expanded, setExpanded] = useState(false);

  if (!reasoningText) return null;

  const lines = reasoningText.split("\n");
  const preview = lines.slice(-3).join("\n");

  return (
    <div className="px-5 py-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex w-full items-center gap-2 text-left"
      >
        <svg
          className={`h-3.5 w-3.5 text-[var(--iris-text-muted)] transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--iris-text-muted)]">
          AI 推理过程
        </span>
      </button>
      <div
        className={`overflow-hidden transition-all ${
          expanded ? "max-h-64" : "max-h-16"
        }`}
      >
        <div className="overflow-y-auto rounded-lg bg-[var(--iris-surface)] p-3">
          <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-[var(--iris-text-secondary)]">
            {expanded ? reasoningText : preview}
          </pre>
        </div>
      </div>
    </div>
  );
}
