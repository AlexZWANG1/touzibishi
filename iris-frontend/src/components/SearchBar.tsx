"use client";

import { useEffect, useRef } from "react";

export type AnalysisMode = "analysis" | "learning";

interface SearchBarProps {
  value: string;
  mode: AnalysisMode;
  loading?: boolean;
  onChange: (value: string) => void;
  onModeChange: (mode: AnalysisMode) => void;
  onSubmit: () => void | Promise<void>;
}

const PLACEHOLDER = `描述你的研究任务...

例如：深度分析 AAPL 最新财报，重点关注服务业务增长趋势对估值的影响，对比 MSFT 和 GOOGL 的云业务，给出 DCF 模型和交易建议。`;

export function SearchBar({
  value,
  mode,
  loading = false,
  onChange,
  onModeChange,
  onSubmit,
}: SearchBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim() || loading) return;
        void onSubmit();
      }}
      className="prism-input-shell p-4 sm:p-5"
    >
      <textarea
        ref={textareaRef}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!value.trim() || loading) return;
            void onSubmit();
          }
        }}
        placeholder={PLACEHOLDER}
        className="min-h-[72px] max-h-[200px] text-[15px] leading-[1.65] placeholder:text-[var(--t4)]"
        disabled={loading}
      />

      <div className="mt-3 flex flex-col gap-3 border-t border-[var(--b1)] pt-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onModeChange("analysis")}
            className="inline-flex items-center gap-2 rounded-pill border px-3 py-2 text-[12px] font-semibold transition-colors"
            style={{
              borderColor: mode === "analysis" ? "var(--ac)" : "var(--b2)",
              background: mode === "analysis" ? "var(--ac-s)" : "var(--bg)",
              color: mode === "analysis" ? "var(--ac)" : "var(--t2)",
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            深度分析
          </button>
          <button
            type="button"
            onClick={() => onModeChange("learning")}
            className="inline-flex items-center gap-2 rounded-pill border px-3 py-2 text-[12px] font-semibold transition-colors"
            style={{
              borderColor: mode === "learning" ? "var(--ac)" : "var(--b2)",
              background: mode === "learning" ? "var(--ac-s)" : "var(--bg)",
              color: mode === "learning" ? "var(--ac)" : "var(--t2)",
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            学习模式
          </button>
        </div>

        <div className="text-[12px] text-[var(--t4)] sm:ml-auto">Shift+Enter 换行 · Enter 发送</div>

        <button
          type="submit"
          disabled={!value.trim() || loading}
          aria-label="提交分析"
          className="inline-flex h-10 w-10 items-center justify-center rounded-[14px] border-0 bg-[var(--ac)] text-white transition-all disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
              aria-hidden="true"
            />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}
