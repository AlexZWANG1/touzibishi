"use client";

import { useRef, useEffect, useMemo, useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";

/**
 * Strip <thinking> tag artifacts from text.
 */
function stripThinking(text: string): string {
  let clean = text;
  clean = clean.replace(/<thinking>[\s\S]*?<\/thinking>/g, "");
  clean = clean.replace(/<thinking>[\s\S]*$/g, "");
  clean = clean.replace(/^[^<]*?(?:inking|hinking|thinking)>\s*/g, "");
  clean = clean.replace(/<\/thinking>/g, "");
  clean = clean.replace(/<thinking\s*$/g, "");
  return clean.trim();
}

interface ChatSegment {
  role: "ai" | "user";
  content: string;
}

/**
 * Split accumulated text into chat segments.
 *
 * The store wraps each user message with <!---TURN---> sentinels:
 *   [AI text] <!---TURN---> user msg <!---TURN---> [AI text] ...
 *
 * Split on the sentinel → even indices are AI, odd indices are user.
 * No regex, no collision with markdown.
 */
const TURN_SENTINEL = "<!---TURN--->";

function splitIntoChatSegments(text: string): ChatSegment[] {
  if (!text) return [];

  const parts = text.split(TURN_SENTINEL);
  const segments: ChatSegment[] = [];

  for (let i = 0; i < parts.length; i++) {
    const content = parts[i].trim();
    if (!content) continue;
    segments.push({
      role: i % 2 === 0 ? "ai" : "user",
      content,
    });
  }

  return segments;
}

/** Streaming dots animation */
function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-[3px] ml-1">
      <span className="inline-block w-[5px] h-[5px] rounded-full bg-[var(--iris-accent)] animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="inline-block w-[5px] h-[5px] rounded-full bg-[var(--iris-accent)] animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="inline-block w-[5px] h-[5px] rounded-full bg-[var(--iris-accent)] animate-bounce" style={{ animationDelay: "300ms" }} />
    </span>
  );
}

/** AI avatar icon */
function AIAvatar() {
  return (
    <div
      className="flex-shrink-0 flex items-center justify-center"
      role="img"
      aria-label="AI Assistant"
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        background: "rgba(245,128,37,0.15)",
        border: "1px solid rgba(245,128,37,0.3)",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--iris-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <title>AI</title>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    </div>
  );
}

export function ChatPanel() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const pageState = useAnalysisStore((s) => s.pageState);
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);
  const sendSteering = useAnalysisStore((s) => s.sendSteering);
  const continueAnalysis = useAnalysisStore((s) => s.continueAnalysis);
  const resumeAnalysis = useAnalysisStore((s) => s.resumeAnalysis);
  const respondToInput = useAnalysisStore((s) => s.respondToInput);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const resumable = useAnalysisStore((s) => s.resumable);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = useState("");
  const [resumeLoading, setResumeLoading] = useState(false);

  const isStreaming = pageState === "RUNNING";
  const cleanText = useMemo(() => stripThinking(reasoningText), [reasoningText]);
  const segments = useMemo(() => splitIntoChatSegments(cleanText), [cleanText]);

  // Auto-scroll on new content — only if user is near the bottom
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (isNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [cleanText, pendingQuestion]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = inputValue.trim();
      if (!trimmed) return;

      if (isReplay && resumable) {
        setResumeLoading(true);
        try {
          await resumeAnalysis(trimmed);
        } finally {
          setResumeLoading(false);
        }
      } else if (pageState === "RUNNING") {
        sendSteering(trimmed);
      } else {
        continueAnalysis(trimmed);
      }
      setInputValue("");
    },
    [inputValue, pageState, isReplay, resumable, sendSteering, continueAnalysis, resumeAnalysis]
  );

  const handleOptionClick = useCallback(
    (option: string) => {
      respondToInput(option);
    },
    [respondToInput]
  );

  const isInputDisabled =
    (pageState === "WAITING") ||
    resumeLoading ||
    (isReplay && !resumable);

  const placeholder =
    isReplay && !resumable
      ? "此对话无法恢复，请发起新分析"
      : isReplay && resumable
        ? "继续对话..."
        : pageState === "RUNNING"
          ? "引导分析方向..."
          : "发送消息...";

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto"
        style={{ padding: "20px 24px 12px" }}
      >
        {/* Empty state */}
        {segments.length === 0 && !isStreaming && pageState === "IDLE" && (
          <div className="flex h-full items-center justify-center">
            <p className="font-mono text-[13px] text-[var(--iris-text-muted)]">
              等待回复...
            </p>
          </div>
        )}

        {/* Streaming with no content yet */}
        {segments.length === 0 && isStreaming && (
          <div className="flex items-start gap-3 mb-5">
            <AIAvatar />
            <div className="flex-1 min-w-0 pt-1">
              <span className="text-[12px] text-[var(--iris-text-muted)] font-mono">思考中</span>
              <StreamingDots />
            </div>
          </div>
        )}

        {/* Message bubbles */}
        <div className="flex flex-col gap-5">
          {segments.map((seg, i) => {
            const isLastAI = seg.role === "ai" && i === segments.length - 1;
            return seg.role === "user" ? (
              /* User message — right aligned */
              <div key={i} className="flex justify-end">
                <div
                  style={{
                    maxWidth: "75%",
                    padding: "10px 14px",
                    borderRadius: "16px 16px 4px 16px",
                    background: "var(--iris-accent)",
                    color: "#fff",
                    fontSize: 14,
                    lineHeight: 1.6,
                    wordBreak: "break-word",
                  }}
                >
                  {seg.content}
                </div>
              </div>
            ) : (
              /* AI message — left aligned with avatar */
              <div key={i} className="flex items-start gap-3">
                <AIAvatar />
                <div className="flex-1 min-w-0 pt-0.5">
                  <div className="prose-iris">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {seg.content}
                    </ReactMarkdown>
                  </div>
                  {isLastAI && isStreaming && (
                    <span className="inline-block mt-1">
                      <StreamingDots />
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Pending question — shown inline as a special AI message */}
        {pageState === "WAITING" && pendingQuestion && (
          <div className="flex items-start gap-3 mt-5">
            <AIAvatar />
            <div className="flex-1 min-w-0">
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "12px",
                  background: "rgba(245,128,37,0.08)",
                  border: "1px solid rgba(245,128,37,0.2)",
                }}
              >
                <p style={{ fontSize: 14, color: "var(--iris-text)", margin: 0, lineHeight: 1.6 }}>
                  {pendingQuestion.question}
                </p>
                {pendingQuestion.context && (
                  <p style={{ fontSize: 12, color: "var(--iris-text-muted)", margin: "6px 0 0 0" }}>
                    {pendingQuestion.context}
                  </p>
                )}
                <div className="flex flex-wrap gap-2 mt-3">
                  {pendingQuestion.options.map((opt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleOptionClick(opt)}
                      className="font-mono transition-colors hover:bg-[var(--iris-accent)] hover:text-white focus:outline-2 focus:outline-offset-2 focus:outline-[var(--iris-accent)] active:scale-95"
                      style={{
                        fontSize: 12,
                        border: "1px solid rgba(245,128,37,0.3)",
                        borderRadius: "8px",
                        background: "transparent",
                        color: "var(--iris-accent)",
                        padding: "6px 12px",
                        cursor: "pointer",
                      }}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input area — always at bottom */}
      <div
        className="flex-shrink-0 border-t border-[var(--iris-border)]"
        style={{ padding: "12px 24px 16px" }}
      >
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={placeholder}
            disabled={isInputDisabled}
            className="flex-1 min-w-0 bg-[var(--iris-surface)] border border-[var(--iris-border)] text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              height: 40,
              padding: "0 14px",
              fontSize: 14,
              borderRadius: "10px",
              caretColor: "var(--iris-accent)",
            }}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isInputDisabled}
            className="flex-shrink-0 flex items-center justify-center transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              width: 40,
              height: 40,
              borderRadius: "10px",
              border: "none",
              background:
                !inputValue.trim() || isInputDisabled
                  ? "var(--iris-surface)"
                  : "var(--iris-accent)",
              color:
                !inputValue.trim() || isInputDisabled
                  ? "var(--iris-text-muted)"
                  : "#fff",
              cursor: !inputValue.trim() || isInputDisabled ? "not-allowed" : "pointer",
            }}
          >
            {resumeLoading ? (
              <span
                className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-t-transparent"
                style={{ borderColor: "currentColor", borderTopColor: "transparent" }}
              />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 19V5m0 0l-7 7m7-7l7 7" />
              </svg>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
