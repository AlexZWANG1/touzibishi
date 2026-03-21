"use client";

import { useMemo, useState } from "react";
import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { StreamingTimeline } from "./StreamingTimeline";
import { CalibrationSummary } from "./CalibrationSummary";

type DebugTab = "logs" | "memory";

const TABS: { key: DebugTab; label: string }[] = [
  { key: "logs", label: "日志" },
  { key: "memory", label: "记忆" },
];

export function DebugPanel() {
  const [activeTab, setActiveTab] = useState<DebugTab>("logs");
  const pageState = useAnalysisStore((s) => s.pageState);

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 gap-2 border-b border-[var(--b1)] px-4 py-3">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            data-active={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="prism-pill-tab"
          >
            {tab.label}
            {activeTab === tab.key && (
              <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-[var(--iris-accent)]" />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
        {pageState === "IDLE" ? (
          <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg)] p-4 text-center text-[13px] text-[var(--t3)]">
            等待分析启动，Prism 会在这里回放工具调用和记忆命中。
          </div>
        ) : activeTab === "logs" ? (
          <LogsTab />
        ) : (
          <MemoryTab />
        )}
      </div>
    </div>
  );
}

function LogsTab() {
  return (
    <div className="prism-panel h-full min-h-[240px] overflow-hidden">
      <StreamingTimeline />
    </div>
  );
}

function MemoryTab() {
  const memoryPanel = useAnalysisStore((s) => s.memoryPanel);
  const timeline = useAnalysisStore((s) => s.timeline);

  const memoryEvents = useMemo(
    () =>
      timeline.filter((event) =>
        [
          "recall",
          "recall_memory",
          "remember",
          "save_memory",
          "search_knowledge",
          "memory_search",
          "check_calibration",
        ].includes(event.tool),
      ),
    [timeline],
  );

  const hasCalibration =
    memoryPanel.calibrationHits > 0 ||
    memoryPanel.calibrationMisses > 0 ||
    memoryPanel.recentRecalls.length > 0;

  if (!hasCalibration && memoryEvents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg)] p-4 text-center text-[13px] text-[var(--t3)]">
        当前分析还没有命中记忆或校准记录。
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {memoryEvents.length > 0 && (
        <section className="prism-panel p-4">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
            Memory Events
          </h3>
          <div className="mt-3 space-y-2">
            {memoryEvents.map((event) => (
              <div
                key={event.id}
                className="flex items-start gap-3 rounded-md bg-[var(--bg)] px-3 py-2"
              >
                <span
                  className="mt-1 inline-block h-2 w-2 rounded-full"
                  style={{
                    background:
                      event.status === "error"
                        ? "var(--red)"
                        : event.status === "running"
                          ? "var(--ac)"
                          : "var(--cy)",
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] font-medium text-[var(--t1)]">{event.tool}</div>
                  <div className="mt-1 text-[12px] leading-[1.6] text-[var(--t3)]">{event.message}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {hasCalibration && (
        <section className="prism-panel p-4">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
            Calibration
          </h3>
          <div className="mt-3">
            <CalibrationSummary
              hits={memoryPanel.calibrationHits}
              misses={memoryPanel.calibrationMisses}
              recentRecalls={memoryPanel.recentRecalls}
            />
          </div>
        </section>
      )}
    </div>
  );
}
