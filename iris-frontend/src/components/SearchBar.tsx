"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { startAnalysis } from "@/utils/api";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed || loading) return;

      setLoading(true);
      try {
        const res = await startAnalysis({ query: trimmed });
        router.push(`/analysis/${res.analysisId}`);
      } catch (err) {
        console.error("Failed to start analysis:", err);
        setLoading(false);
      }
    },
    [query, loading, router]
  );

  return (
    <form onSubmit={handleSubmit} className="relative mx-auto max-w-2xl">
      <div className="relative">
        <svg
          className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--iris-text-muted)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
          />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入 ticker 或公司名称，例如 AAPL、腾讯..."
          className="w-full rounded-xl border border-[var(--iris-border)] bg-[var(--iris-surface)] py-3.5 pl-12 pr-28 text-base text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] transition-all focus:border-[var(--iris-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--iris-accent)]/20"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-[var(--iris-accent)] px-5 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--iris-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          ) : (
            "分析"
          )}
        </button>
      </div>
    </form>
  );
}
