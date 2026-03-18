"use client";

import { useState, useCallback } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

export function PendingQuestionCard() {
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);
  const respondToInput = useAnalysisStore((s) => s.respondToInput);
  const [customResponse, setCustomResponse] = useState("");

  const handleOptionClick = useCallback(
    (option: string) => {
      respondToInput(option);
    },
    [respondToInput]
  );

  const handleCustomSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = customResponse.trim();
      if (!trimmed) return;
      respondToInput(trimmed);
      setCustomResponse("");
    },
    [customResponse, respondToInput]
  );

  if (!pendingQuestion) return null;

  return (
    <div className="rounded-xl border border-[var(--event-user)]/30 bg-[var(--event-user)]/5 p-4">
      <div className="mb-3 flex items-start gap-2">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[var(--event-user)]/20">
          <span className="text-xs text-[var(--event-user)]">?</span>
        </div>
        <p className="text-sm font-medium text-[var(--iris-text)]">
          {pendingQuestion.question}
        </p>
      </div>

      {pendingQuestion.context && (
        <p className="mb-3 ml-7 text-xs text-[var(--iris-text-secondary)]">
          {pendingQuestion.context}
        </p>
      )}

      {pendingQuestion.options.length > 0 && (
        <div className="mb-3 ml-7 flex flex-wrap gap-2">
          {pendingQuestion.options.map((option, idx) => (
            <button
              key={idx}
              onClick={() => handleOptionClick(option)}
              className="rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] px-3 py-1.5 text-sm text-[var(--iris-text-secondary)] transition-all hover:border-[var(--iris-accent)] hover:text-[var(--iris-text)]"
            >
              {option}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleCustomSubmit} className="ml-7 flex gap-2">
        <input
          type="text"
          value={customResponse}
          onChange={(e) => setCustomResponse(e.target.value)}
          placeholder="或输入自定义回复..."
          className="flex-1 rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] px-3 py-2 text-sm text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={!customResponse.trim()}
          className="rounded-lg bg-[var(--event-user)] px-3 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-40"
        >
          回复
        </button>
      </form>
    </div>
  );
}
