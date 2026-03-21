"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function FundamentalsPanel() {
  const sections = useAnalysisStore((s) => s.fundamentalsPanel.sections);
  const pageState = useAnalysisStore((s) => s.pageState);
  const [activeIdx, setActiveIdx] = useState(0);

  if (sections.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t4)]">研究面板</div>
        <p className="mt-2 text-[13px] text-[var(--t3)]">
          {pageState === "RUNNING" ? "研究进行中，章节将逐步出现..." : "等待研究产出..."}
        </p>
      </div>
    );
  }

  const current = sections[Math.min(activeIdx, sections.length - 1)];

  return (
    <div className="flex h-full">
      {/* Section nav */}
      <nav className="w-48 shrink-0 overflow-y-auto border-r border-[var(--b1)] bg-[var(--bg-2)]">
        <div className="px-3 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--t4)]">
            研究章节
          </div>
        </div>
        {sections.map((section, idx) => (
          <button
            key={`${section.title}-${idx}`}
            type="button"
            onClick={() => setActiveIdx(idx)}
            className={`w-full px-3 py-2.5 text-left text-[12px] leading-[1.5] transition-colors ${
              idx === activeIdx
                ? "bg-[var(--ac-s)] font-medium text-[var(--ac)]"
                : "text-[var(--t2)] hover:bg-[var(--bg-hover)]"
            }`}
          >
            <span className="mr-1.5 inline-block font-mono text-[10px] text-[var(--t4)]">
              {String(idx + 1).padStart(2, "0")}
            </span>
            {section.title}
          </button>
        ))}
        {pageState === "RUNNING" && (
          <div className="px-3 py-2.5 text-[11px] text-[var(--t4)]">
            <span className="prism-shimmer inline-block h-3 w-20 rounded" />
          </div>
        )}
      </nav>

      {/* Content area */}
      <article className="min-w-0 flex-1 overflow-y-auto px-6 py-5 sm:px-8">
        <h2 className="mb-4 text-[15px] font-semibold text-[var(--t1)]">
          {current.title}
        </h2>
        <div className="prose prose-sm max-w-none text-[var(--t1)]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {current.content}
          </ReactMarkdown>
        </div>
      </article>
    </div>
  );
}
