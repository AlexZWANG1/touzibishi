"use client";

import { useState, useCallback } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

const PLACEHOLDERS: Record<string, string> = {
  IDLE: "继续对话... 比如'WACC 改成 12% 再算一遍'",
  RUNNING: "引导分析方向，例如：重点关注 FCF margin...",
  WAITING: "等待回复问题...",
  COMPLETE: "继续对话... 比如'WACC 改成 12% 再算一遍'",
};

export function SteeringInput() {
  const [message, setMessage] = useState("");
  const sendSteering = useAnalysisStore((s) => s.sendSteering);
  const continueAnalysis = useAnalysisStore((s) => s.continueAnalysis);
  const pageState = useAnalysisStore((s) => s.pageState);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = message.trim();
      if (!trimmed) return;

      if (pageState === "RUNNING") {
        sendSteering(trimmed);
      } else {
        // COMPLETE or IDLE with an existing analysis — continue the conversation
        continueAnalysis(trimmed);
      }
      setMessage("");
    },
    [message, sendSteering, continueAnalysis, pageState]
  );

  const isDisabled = pageState === "WAITING";
  const placeholder = PLACEHOLDERS[pageState] || PLACEHOLDERS.RUNNING;

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center"
      style={{ gap: 6 }}
    >
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={placeholder}
        disabled={isDisabled}
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
        disabled={!message.trim() || isDisabled}
        className="flex flex-shrink-0 items-center justify-center border-none disabled:cursor-not-allowed disabled:opacity-30"
        style={{
          width: 28,
          height: 28,
          borderRadius: 0,
          background:
            !message.trim() || isDisabled
              ? "var(--bg-w)"
              : "var(--ac)",
          color:
            !message.trim() || isDisabled
              ? "var(--t3)"
              : "var(--bg)",
          cursor: !message.trim() || isDisabled ? "not-allowed" : "pointer",
        }}
      >
        <svg
          style={{ width: 12, height: 12 }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 19V5m0 0l-7 7m7-7l7 7" />
        </svg>
      </button>
    </form>
  );
}
