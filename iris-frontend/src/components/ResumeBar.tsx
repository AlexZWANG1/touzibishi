"use client";

import { useState, useCallback } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function ResumeBar() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const resumeAnalysis = useAnalysisStore((s) => s.resumeAnalysis);
  const resumable = useAnalysisStore((s) => s.resumable);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = message.trim();
      if (!trimmed || !resumable || loading) return;

      setLoading(true);
      try {
        await resumeAnalysis(trimmed);
        setMessage("");
      } finally {
        setLoading(false);
      }
    },
    [message, resumable, loading, resumeAnalysis]
  );

  if (!resumable) {
    return (
      <div
        className="flex items-center justify-center py-1 font-mono text-[11px]"
        style={{ color: "var(--t3)" }}
      >
        此对话无法恢复（旧数据），请发起新分析
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center" style={{ gap: 6 }}>
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="继续对话... 比如'WACC 改成 12% 再算一遍'"
        disabled={loading}
        className="min-w-0 flex-1 border border-[var(--b1)] bg-transparent font-sans text-[var(--t1)] placeholder:text-[var(--t3)] focus:border-[var(--ac)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
        style={{
          height: 28,
          padding: "0 8px",
          fontSize: 11,
          borderRadius: 0,
          caretColor: "var(--ac)",
        }}
      />

      <button
        type="submit"
        disabled={!message.trim() || loading}
        className="flex flex-shrink-0 items-center justify-center border-none disabled:cursor-not-allowed disabled:opacity-30"
        style={{
          height: 28,
          padding: "0 10px",
          borderRadius: 0,
          background:
            !message.trim() || loading
              ? "var(--bg-w)"
              : "var(--ac)",
          color:
            !message.trim() || loading
              ? "var(--t3)"
              : "var(--bg)",
          cursor: !message.trim() || loading ? "not-allowed" : "pointer",
          fontSize: 11,
          fontFamily: "var(--font-mono, monospace)",
        }}
      >
        {loading ? (
          <span className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 animate-spin border border-t-transparent"
              style={{ borderColor: "currentColor", borderTopColor: "transparent" }}
            />
            恢复中
          </span>
        ) : (
          "继续对话"
        )}
      </button>
    </form>
  );
}
