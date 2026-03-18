"use client";

import { useState, useCallback } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function SteeringInput() {
  const [message, setMessage] = useState("");
  const sendSteering = useAnalysisStore((s) => s.sendSteering);
  const pageState = useAnalysisStore((s) => s.pageState);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = message.trim();
      if (!trimmed) return;
      sendSteering(trimmed);
      setMessage("");
    },
    [message, sendSteering]
  );

  const isDisabled = pageState !== "RUNNING" && pageState !== "COMPLETE";

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={
          pageState === "COMPLETE"
            ? "分析已完成。输入新问题继续探索..."
            : "引导分析方向，例如：重点关注 FCF margin..."
        }
        disabled={isDisabled}
        className="flex-1 rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] px-3.5 py-2.5 text-sm text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] transition-colors focus:border-[var(--iris-accent)] focus:outline-none disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={!message.trim() || isDisabled}
        className="flex-shrink-0 rounded-lg bg-[var(--iris-accent)] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--iris-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
      </button>
    </form>
  );
}
