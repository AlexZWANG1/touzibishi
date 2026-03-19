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
  render: "RENDER",
  raw: "RAW",
  edit: "EDIT",
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
      <div className="flex items-center justify-between border-b border-[var(--iris-border)] px-[10px] py-[5px]">
        <div>
          <h2 className="font-mono text-[11px] text-[var(--iris-text)]">
            {fileContent.path}
          </h2>
        </div>
        <div className="flex items-center gap-[4px]">
          {/* Mode switcher */}
          <div className="flex border border-[var(--iris-border)]">
            {(Object.keys(modeLabels) as MemoryViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                className={`px-[8px] py-[3px] font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  viewMode === mode
                    ? "bg-[var(--iris-accent)] text-white"
                    : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
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
              className="bg-[var(--iris-accent)] px-[10px] py-[3px] font-mono text-[10px] uppercase tracking-wider text-white transition-colors disabled:opacity-50"
            >
              {saving ? "SAVING..." : "SAVE"}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === "render" && (
          <div className="prose-iris p-[12px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {fileContent.content}
            </ReactMarkdown>
          </div>
        )}

        {viewMode === "raw" && (
          <pre className="p-[12px] font-mono text-[11px] leading-relaxed text-[var(--iris-text-secondary)]">
            {fileContent.content}
          </pre>
        )}

        {viewMode === "edit" && (
          <textarea
            value={editContent}
            onChange={(e) => onEditContentChange(e.target.value)}
            className="h-full w-full resize-none border-0 bg-transparent p-[12px] font-mono text-[11px] leading-relaxed text-[var(--iris-text)] outline-none"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  );
}
