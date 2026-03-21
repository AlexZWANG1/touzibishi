"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MemoryFileContent, MemoryViewMode } from "@/types/memory";

interface MemoryFileViewerProps {
  fileContent: MemoryFileContent;
  viewMode: MemoryViewMode;
  editContent: string;
  saving: boolean;
  onViewModeChange: (mode: MemoryViewMode) => void;
  onEditContentChange: (content: string) => void;
  onSave: () => void;
}

const MODE_LABELS: Record<MemoryViewMode, string> = {
  render: "渲染",
  raw: "源码",
  edit: "编辑",
};

export function MemoryFileViewer({
  fileContent,
  viewMode,
  editContent,
  saving,
  onViewModeChange,
  onEditContentChange,
  onSave,
}: MemoryFileViewerProps) {
  const hasUnsavedChanges = viewMode === "edit" && editContent !== fileContent.content;

  function handleModeChange(mode: MemoryViewMode) {
    if (hasUnsavedChanges && mode !== "edit") {
      const confirmed = window.confirm("You have unsaved changes. Discard? / 有未保存的修改，确认放弃？");
      if (!confirmed) return;
    }
    onViewModeChange(mode);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--b1)] px-6 py-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
              Memory File
            </div>
            <div className="mt-2 truncate font-mono text-[13px] text-[var(--t1)]">{fileContent.path}</div>
          </div>

          <div className="flex items-center gap-2">
            {(Object.keys(MODE_LABELS) as MemoryViewMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => handleModeChange(mode)}
                className="rounded-pill px-3 py-1.5 text-[12px] font-medium transition-colors"
                style={{
                  background: viewMode === mode ? "var(--ac)" : "var(--bg-2)",
                  color: viewMode === mode ? "#ffffff" : "var(--t2)",
                }}
              >
                {MODE_LABELS[mode]}
              </button>
            ))}

            {viewMode === "edit" && (
              <button
                type="button"
                onClick={onSave}
                disabled={saving}
                className="rounded-[14px] bg-[var(--ac)] px-4 py-2 text-[12px] font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? "Saving..." : "Save"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto bg-[rgba(255,255,255,0.65)]">
        {viewMode === "render" && (
          <div className="prose-reader px-6 py-8">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{fileContent.content}</ReactMarkdown>
          </div>
        )}

        {viewMode === "raw" && (
          <pre className="px-6 py-8 font-mono text-[12px] leading-[1.8] text-[var(--t2)]">{fileContent.content}</pre>
        )}

        {viewMode === "edit" && (
          <textarea
            value={editContent}
            onChange={(event) => onEditContentChange(event.target.value)}
            className="h-full min-h-full w-full resize-none border-0 bg-transparent px-6 py-8 font-mono text-[12px] leading-[1.8] text-[var(--t1)] outline-none"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  );
}
