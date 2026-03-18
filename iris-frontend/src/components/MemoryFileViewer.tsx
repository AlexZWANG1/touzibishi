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

const modeLabels: Record<MemoryViewMode, string> = {
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
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--iris-border)] px-5 py-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--iris-text)]">
            {fileContent.path}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {/* Mode switcher */}
          <div className="flex rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)]">
            {(Object.keys(modeLabels) as MemoryViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === mode
                    ? "bg-[var(--iris-accent)] text-white"
                    : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
                } ${mode === "render" ? "rounded-l-lg" : ""} ${
                  mode === "edit" ? "rounded-r-lg" : ""
                }`}
              >
                {modeLabels[mode]}
              </button>
            ))}
          </div>

          {viewMode === "edit" && (
            <button
              onClick={onSave}
              disabled={saving}
              className="rounded-lg bg-[var(--iris-accent)] px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--iris-accent-hover)] disabled:opacity-50"
            >
              {saving ? "保存中..." : "保存"}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === "render" && (
          <div className="prose-iris p-6">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {fileContent.content}
            </ReactMarkdown>
          </div>
        )}

        {viewMode === "raw" && (
          <pre className="p-6 font-mono text-sm leading-relaxed text-[var(--iris-text-secondary)]">
            {fileContent.content}
          </pre>
        )}

        {viewMode === "edit" && (
          <textarea
            value={editContent}
            onChange={(e) => onEditContentChange(e.target.value)}
            className="h-full w-full resize-none bg-transparent p-6 font-mono text-sm leading-relaxed text-[var(--iris-text)] outline-none"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  );
}
