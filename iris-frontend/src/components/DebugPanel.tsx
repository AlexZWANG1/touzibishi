"use client";

import { useState, useMemo } from "react";
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
      {/* Tab bar */}
      <div className="flex flex-shrink-0 border-b border-[var(--iris-border)]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-[6px] font-mono text-[11px] font-medium transition-colors ${
              activeTab === tab.key
                ? "text-[var(--iris-accent)] border-b border-[var(--iris-accent)]"
                : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
            }`}
            style={{ cursor: "pointer", background: "transparent", border: "none", borderBottom: activeTab === tab.key ? "1px solid var(--iris-accent)" : "1px solid transparent" }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {pageState === "IDLE" ? (
          <div className="flex h-full items-center justify-center">
            <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
              WAITING...
            </p>
          </div>
        ) : (
          <>
            {activeTab === "logs" && <LogsTab />}
            {activeTab === "memory" && <MemoryTab />}
          </>
        )}
      </div>
    </div>
  );
}

/** Logs tab — tool call timeline */
function LogsTab() {
  return (
    <div className="px-[6px] py-[4px]">
      <StreamingTimeline />
    </div>
  );
}

/** Memory tab — recall history and calibration */
function MemoryTab() {
  const memoryPanel = useAnalysisStore((s) => s.memoryPanel);

  const hasMemory =
    memoryPanel.calibrationHits > 0 ||
    memoryPanel.calibrationMisses > 0 ||
    memoryPanel.recentRecalls.length > 0;

  // Also show memory-related tool calls from timeline
  const timeline = useAnalysisStore((s) => s.timeline);
  const memoryEvents = useMemo(
    () =>
      timeline.filter(
        (ev) =>
          ev.tool === "recall" ||
          ev.tool === "recall_memory" ||
          ev.tool === "remember" ||
          ev.tool === "save_memory" ||
          ev.tool === "search_knowledge" ||
          ev.tool === "memory_search" ||
          ev.tool === "check_calibration"
      ),
    [timeline]
  );

  if (!hasMemory && memoryEvents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">
          暂无记忆活动
        </p>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-4">
      {/* Memory events */}
      {memoryEvents.length > 0 && (
        <div>
          <h4
            className="font-mono uppercase mb-2"
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--iris-accent)",
              letterSpacing: "0.06em",
            }}
          >
            记忆操作
          </h4>
          <div className="space-y-1">
            {memoryEvents.map((ev) => (
              <div
                key={ev.id}
                className="flex items-center gap-2 font-mono"
                style={{ fontSize: 11 }}
              >
                <span
                  className="flex-shrink-0 inline-block w-1.5 h-1.5 rounded-full"
                  style={{
                    background:
                      ev.status === "error"
                        ? "#EF4444"
                        : ev.status === "running"
                          ? "var(--iris-accent)"
                          : "var(--iris-data)",
                  }}
                />
                <span style={{ color: "var(--iris-data)" }}>
                  {ev.tool === "recall" || ev.tool === "recall_memory"
                    ? "检索"
                    : ev.tool === "remember" || ev.tool === "save_memory"
                      ? "写入"
                      : ev.tool === "check_calibration"
                        ? "校准"
                        : "搜索"}
                </span>
                <span className="truncate text-[var(--iris-text-secondary)]">
                  {ev.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Calibration */}
      {hasMemory && (
        <div>
          <h4
            className="font-mono uppercase mb-2"
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--iris-accent)",
              letterSpacing: "0.06em",
            }}
          >
            校准数据
          </h4>
          <CalibrationSummary
            hits={memoryPanel.calibrationHits}
            misses={memoryPanel.calibrationMisses}
            recentRecalls={memoryPanel.recentRecalls}
          />
        </div>
      )}
    </div>
  );
}
