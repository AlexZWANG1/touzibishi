"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function FundamentalsPanel() {
  const { title, content, loading } = useAnalysisStore((s) => s.fundamentalsPanel);
  const pageState = useAnalysisStore((s) => s.pageState);

  if (!content) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t4)]">
          研究面板
        </div>
        <p className="mt-2 text-[13px] text-[var(--t3)]">
          {pageState === "RUNNING"
            ? "深度研究进行中，报告将在研究完成后出现..."
            : "等待研究产出..."}
        </p>
        {pageState === "RUNNING" && (
          <div className="mt-4 flex flex-col gap-3 w-full max-w-xl">
            <div className="prism-shimmer h-4 w-3/4 rounded" />
            <div className="prism-shimmer h-4 w-full rounded" />
            <div className="prism-shimmer h-4 w-5/6 rounded" />
            <div className="prism-shimmer h-4 w-2/3 rounded" />
          </div>
        )}
      </div>
    );
  }

  return (
    <article className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-6 py-8 sm:px-10">
        {title && (
          <h1 className="mb-6 text-xl font-bold leading-tight text-[var(--t1)]">
            {title}
          </h1>
        )}
        <div className="prose prose-sm max-w-none text-[var(--t1)] prose-headings:text-[var(--t1)] prose-headings:font-semibold prose-h2:text-[16px] prose-h2:mt-8 prose-h2:mb-3 prose-h3:text-[14px] prose-h3:mt-6 prose-h3:mb-2 prose-p:text-[13px] prose-p:leading-[1.8] prose-li:text-[13px] prose-li:leading-[1.7] prose-strong:text-[var(--t1)] prose-blockquote:border-[var(--ac)] prose-blockquote:text-[var(--t2)] prose-hr:border-[var(--b1)] prose-a:text-[var(--ac)] prose-code:text-[12px] prose-code:bg-[var(--bg-2)] prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </article>
  );
}
