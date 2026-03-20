"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { startAnalysis } from "@/utils/api";

type AnalysisMode = "analysis" | "learning";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<AnalysisMode>("analysis");
  const router = useRouter();

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed || loading) return;

      setLoading(true);
      try {
        const res = await startAnalysis({ query: trimmed, mode });
        router.push(`/analysis/${res.analysisId}`);
      } catch (err) {
        console.error("Failed to start:", err);
        setLoading(false);
      }
    },
    [query, loading, router, mode]
  );

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div
        className="relative flex items-center border focus-within:!border-[var(--iris-accent)]"
        style={{
          height: "28px",
          backgroundColor: "transparent",
          borderColor: "var(--iris-border)",
        }}
      >
        {/* Mode toggle */}
        <button
          type="button"
          onClick={() => setMode(mode === "analysis" ? "learning" : "analysis")}
          className="ml-px flex-shrink-0 flex items-center gap-1 px-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider transition-colors"
          style={{
            height: "26px",
            border: "none",
            borderRight: "1px solid var(--iris-border)",
            backgroundColor: mode === "learning" ? "rgba(245,128,37,0.08)" : "transparent",
            color: mode === "learning" ? "var(--iris-accent)" : "var(--iris-text-muted)",
          }}
          title={mode === "analysis" ? "Switch to Learning mode / 切换到学习模式" : "Switch to Analysis mode / 切换到分析模式"}
        >
          {mode === "analysis" ? (
            <>
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              ANL
            </>
          ) : (
            <>
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              LRN
            </>
          )}
        </button>

        {/* Search icon */}
        <svg
          className="ml-1.5 h-3 w-3 flex-shrink-0"
          style={{ color: "var(--iris-text-muted)" }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
          />
        </svg>

        <input
          id="analysis-query"
          name="analysis_query"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={mode === "analysis" ? "TICKER / COMPANY NAME..." : "复盘目标，如「复盘 NVDA」..."}
          className="h-full flex-1 bg-transparent px-1.5 font-mono text-[12px] outline-none placeholder:text-[var(--iris-text-muted)]"
          style={{
            color: "var(--iris-text)",
            caretColor: "var(--iris-accent)",
          }}
          disabled={loading}
        />

        <button
          type="submit"
          disabled={!query.trim() || loading}
          aria-label={loading ? "Analyzing..." : "Start analysis"}
          className="flex-shrink-0 flex items-center justify-center font-mono text-[11px] font-bold uppercase tracking-wider disabled:cursor-not-allowed disabled:opacity-30"
          style={{
            height: "28px",
            width: "28px",
            backgroundColor: "var(--iris-accent)",
            color: "#07080C",
          }}
        >
          {loading ? (
            <div
              className="h-2.5 w-2.5 animate-spin border border-t-transparent"
              style={{ borderColor: "#07080C", borderTopColor: "transparent" }}
            />
          ) : (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="square" strokeLinejoin="miter" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}
