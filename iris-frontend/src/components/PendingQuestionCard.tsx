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
    <div
      style={{
        border: "1px solid var(--iris-accent)",
        background: "var(--iris-accent-glow)",
        padding: 8,
        borderRadius: 0,
      }}
    >
      <p
        className="font-mono"
        style={{
          fontSize: 10,
          fontWeight: 500,
          color: "var(--iris-text)",
          margin: 0,
        }}
      >
        {pendingQuestion.question}
      </p>

      {pendingQuestion.context && (
        <p
          style={{
            fontSize: 9,
            color: "var(--iris-text-muted)",
            margin: "2px 0 0 0",
          }}
        >
          {pendingQuestion.context}
        </p>
      )}

      <div
        className="mt-1.5 flex flex-wrap items-center"
        style={{ gap: 4 }}
      >
        {pendingQuestion.options.map((option, idx) => (
          <button
            key={idx}
            onClick={() => handleOptionClick(option)}
            className="font-mono hover:border-[var(--iris-accent)] hover:text-[var(--iris-text)]"
            style={{
              fontSize: 9,
              border: "1px solid var(--iris-border)",
              borderRadius: 0,
              background: "transparent",
              color: "var(--iris-text-secondary)",
              padding: "2px 6px",
              cursor: "pointer",
            }}
          >
            {option}
          </button>
        ))}

        <form
          onSubmit={handleCustomSubmit}
          className="flex flex-1 items-center"
          style={{ gap: 4, minWidth: 120 }}
        >
          <input
            type="text"
            value={customResponse}
            onChange={(e) => setCustomResponse(e.target.value)}
            placeholder="自定义回复..."
            className="flex-1 font-mono placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
            style={{
              fontSize: 9,
              border: "1px solid var(--iris-border)",
              borderRadius: 0,
              background: "transparent",
              color: "var(--iris-text)",
              padding: "2px 6px",
            }}
          />
          <button
            type="submit"
            disabled={!customResponse.trim()}
            className="font-mono disabled:opacity-30"
            style={{
              fontSize: 9,
              fontWeight: 500,
              border: "none",
              borderRadius: 0,
              background: "var(--iris-accent)",
              color: "var(--iris-bg)",
              padding: "2px 6px",
              cursor: !customResponse.trim() ? "not-allowed" : "pointer",
            }}
          >
            回复
          </button>
        </form>
      </div>
    </div>
  );
}
