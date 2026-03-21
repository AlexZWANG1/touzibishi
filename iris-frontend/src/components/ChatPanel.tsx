"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { PrismLogo } from "./PrismLogo";

interface ChatSegment {
  role: "ai" | "user";
  content: string;
}

const TURN_SENTINEL = "<!---TURN--->";

function stripThinking(text: string): string {
  let clean = text;
  clean = clean.replace(/<thinking>[\s\S]*?<\/thinking>/g, "");
  clean = clean.replace(/<thinking>[\s\S]*$/g, "");
  clean = clean.replace(/^[^<]*?(?:inking|hinking|thinking)>\s*/g, "");
  clean = clean.replace(/<\/thinking>/g, "");
  clean = clean.replace(/<thinking\s*$/g, "");
  return clean.trim();
}

function splitIntoChatSegments(text: string): ChatSegment[] {
  if (!text) return [];

  const segments: ChatSegment[] = [];
  for (const [index, content] of text.split(TURN_SENTINEL).entries()) {
    const trimmed = content.trim();
    if (!trimmed) continue;
    segments.push({
      role: index % 2 === 0 ? "ai" : "user",
      content: trimmed,
    });
  }
  return segments;
}

function StreamingDots() {
  return (
    <span className="ml-2 inline-flex items-center gap-[4px] align-middle">
      {[0, 120, 240].map((delay) => (
        <span
          key={delay}
          className="inline-block h-[6px] w-[6px] animate-bounce rounded-full bg-[var(--ac)]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

function AIAvatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border border-[var(--ac-m)] bg-[var(--ac-s)]">
      <PrismLogo size={16} showWordmark={false} />
    </div>
  );
}

export function ChatPanel() {
  const reasoningText = useAnalysisStore((s) => s.reasoningText);
  const thinkingText = useAnalysisStore((s) => s.thinkingText);
  const pageState = useAnalysisStore((s) => s.pageState);
  const pendingQuestion = useAnalysisStore((s) => s.pendingQuestion);
  const sendSteering = useAnalysisStore((s) => s.sendSteering);
  const continueAnalysis = useAnalysisStore((s) => s.continueAnalysis);
  const resumeAnalysis = useAnalysisStore((s) => s.resumeAnalysis);
  const respondToInput = useAnalysisStore((s) => s.respondToInput);
  const isReplay = useAnalysisStore((s) => s.isReplay);
  const resumable = useAnalysisStore((s) => s.resumable);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [inputValue, setInputValue] = useState("");
  const [resumeLoading, setResumeLoading] = useState(false);
  const [thinkingOpen, setThinkingOpen] = useState(false);

  const isStreaming = pageState === "RUNNING";
  const cleanText = useMemo(() => stripThinking(reasoningText), [reasoningText]);
  const segments = useMemo(() => splitIntoChatSegments(cleanText), [cleanText]);
  const thinkingPreview = useMemo(() => thinkingText.split("\n")[0]?.slice(0, 100) ?? "", [thinkingText]);

  useEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const nearBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120;
    if (nearBottom) {
      scroller.scrollTop = scroller.scrollHeight;
    }
  }, [cleanText, pendingQuestion, thinkingText]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "24px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  }, [inputValue]);

  const handleSubmit = useCallback(
    async (event?: React.FormEvent) => {
      event?.preventDefault();
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
        await sendSteering(trimmed);
      } else {
        await continueAnalysis(trimmed);
      }

      setInputValue("");
    },
    [continueAnalysis, inputValue, isReplay, pageState, resumable, resumeAnalysis, sendSteering],
  );

  const isInputDisabled = pageState === "WAITING" || resumeLoading || (isReplay && !resumable);
  const placeholder =
    isReplay && !resumable
      ? "此历史分析不可恢复，请发起新的研究任务"
      : isReplay && resumable
        ? "继续这轮研究，追加新的问题..."
        : pageState === "RUNNING"
          ? "引导分析方向，可以写得更具体一些..."
          : "继续提问，或让 Prism 深挖某个结论...";

  return (
    <div className="flex h-full flex-col bg-[linear-gradient(180deg,rgba(255,255,255,0.5)_0%,rgba(255,255,255,0.82)_24%,rgba(255,255,255,0.94)_100%)]">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6 sm:px-8">
        <div className="mx-auto max-w-[780px]">
          {thinkingText && (
            <div className="mb-6 overflow-hidden rounded-lg border border-[var(--ac-m)] bg-[var(--ac-s)]">
              <button
                type="button"
                onClick={() => setThinkingOpen((open) => !open)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left"
              >
                <span
                  className="inline-block text-[10px] text-[var(--ac)] transition-transform"
                  style={{ transform: thinkingOpen ? "rotate(90deg)" : "rotate(0deg)" }}
                >
                  ▶
                </span>
                <span className="text-[12px] font-semibold text-[var(--ac)]">Trace</span>
                <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--t3)]">{thinkingPreview}</span>
              </button>
              {thinkingOpen && (
                <pre className="border-t border-[var(--ac-m)] px-4 py-4 font-mono text-[11px] leading-[1.7] text-[var(--t2)]">
                  {thinkingText}
                </pre>
              )}
            </div>
          )}

          {segments.length === 0 && !isStreaming && pageState === "IDLE" && (
            <div className="rounded-[20px] border border-dashed border-[var(--b2)] bg-[var(--bg-w)] px-6 py-10 text-center shadow-card">
              <p className="font-display text-[28px] text-[var(--ink)]">Conversation</p>
              <p className="mt-3 text-[14px] leading-[1.8] text-[var(--t3)]">
                分析开始后，Prism 会把中间推理、关键数据和你的追问整理在这里。
              </p>
            </div>
          )}

          {segments.length === 0 && isStreaming && (
            <div className="mb-6 flex items-start gap-4">
              <AIAvatar />
              <div className="pt-1 text-[13px] text-[var(--t3)]">
                Prism 正在拆解任务<StreamingDots />
              </div>
            </div>
          )}

          <div className="space-y-7">
            {segments.map((segment, index) => {
              const isLastAI = segment.role === "ai" && index === segments.length - 1;

              if (segment.role === "user") {
                return (
                  <div key={`${segment.role}-${index}`} className="flex justify-end">
                    <div
                      className="max-w-[78%] rounded-[20px] px-5 py-3 text-[14px] leading-[1.65] text-white shadow-card"
                      style={{
                        background: "linear-gradient(135deg, var(--ac) 0%, var(--ac-h) 100%)",
                        borderRadius: "20px 20px 6px 20px",
                      }}
                    >
                      {segment.content}
                    </div>
                  </div>
                );
              }

              return (
                <div key={`${segment.role}-${index}`} className="flex items-start gap-4">
                  <AIAvatar />
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="prose-iris rounded-[18px] bg-[var(--bg-w)] px-5 py-4 shadow-card">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{segment.content}</ReactMarkdown>
                    </div>
                    {isLastAI && isStreaming && (
                      <div className="mt-2 text-[12px] text-[var(--t3)]">
                        持续生成中<StreamingDots />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {pageState === "WAITING" && pendingQuestion && (
            <div className="mt-7 flex items-start gap-4">
              <AIAvatar />
              <div className="min-w-0 flex-1 rounded-[18px] border border-[var(--ac-m)] bg-[var(--ac-s)] px-5 py-4 shadow-card">
                <p className="text-[14px] leading-[1.7] text-[var(--t1)]">{pendingQuestion.question}</p>
                {pendingQuestion.context && (
                  <p className="mt-2 text-[12px] leading-[1.7] text-[var(--t3)]">{pendingQuestion.context}</p>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  {pendingQuestion.options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => void respondToInput(option)}
                      className="rounded-pill border border-[var(--ac-m)] bg-white px-3 py-2 text-[12px] font-medium text-[var(--ac)] transition-colors hover:bg-[var(--ac)] hover:text-white"
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 border-t border-[var(--b2)] bg-[rgba(255,255,255,0.9)] px-5 py-4 backdrop-blur sm:px-8">
        <div className="mx-auto max-w-[780px]">
          <form onSubmit={(event) => void handleSubmit(event)} className="prism-input-shell p-3">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSubmit();
                }
              }}
              placeholder={placeholder}
              disabled={isInputDisabled}
              className="min-h-[24px] max-h-[120px] text-[14px] leading-[1.6] placeholder:text-[var(--t4)] disabled:cursor-not-allowed disabled:opacity-60"
            />
            <div className="mt-2 flex items-center gap-3">
              <span className="text-[11px] text-[var(--t4)]">Shift+Enter 换行</span>
              <button
                type="submit"
                disabled={!inputValue.trim() || isInputDisabled}
                className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-full bg-[var(--ac)] text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-35"
              >
                {resumeLoading ? (
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                    <path d="M12 19V5m0 0l-7 7m7-7l7 7" />
                  </svg>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
