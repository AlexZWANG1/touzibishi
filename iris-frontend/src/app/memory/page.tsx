"use client";

import { useMemoryApi } from "@/hooks/useMemoryApi";
import { MemoryFileTree } from "@/components/MemoryFileTree";
import { MemoryFileViewer } from "@/components/MemoryFileViewer";

export default function MemoryPage() {
  const {
    tree,
    selectedFile,
    fileContent,
    viewMode,
    editContent,
    loading,
    saving,
    error,
    selectFile,
    setViewMode,
    setEditContent,
    saveFile,
    refreshTree,
  } = useMemoryApi();

  const hasFiles = Object.values(tree).some((files) => files.length > 0);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] bg-[var(--iris-bg)]">
      {/* Sidebar - File Tree */}
      <div className="w-[240px] shrink-0 border-r border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <div className="flex items-center justify-between border-b border-[var(--iris-border)] px-[10px] py-[6px]">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--iris-accent)]">
            MEMORY FILES
          </h2>
          <button
            onClick={refreshTree}
            className="p-1 text-[var(--iris-text-muted)] transition-colors hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text-secondary)]"
            title="刷新"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
        <div className="overflow-y-auto p-[4px]" style={{ height: "calc(100% - 37px)" }}>
          {loading && !hasFiles ? (
            <div className="flex items-center justify-center py-6">
              <div className="h-3 w-3 animate-spin border border-[var(--iris-accent)] border-t-transparent" />
            </div>
          ) : (
            <MemoryFileTree
              tree={tree}
              selectedType={selectedFile?.memoryType ?? null}
              selectedFilename={selectedFile?.filename ?? null}
              onSelect={selectFile}
            />
          )}
        </div>
      </div>

      {/* Main Content - File Viewer */}
      <div className="flex-1">
        {error && (
          <div className="m-[8px] border border-red-500/20 bg-red-500/5 px-[10px] py-[6px] font-mono text-[11px] text-red-400">
            {error}
          </div>
        )}
        {selectedFile && fileContent ? (
          <MemoryFileViewer
            fileContent={fileContent}
            viewMode={viewMode}
            editContent={editContent}
            saving={saving}
            onViewModeChange={setViewMode}
            onEditContentChange={setEditContent}
            onSave={saveFile}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <svg className="mx-auto mb-[6px] h-8 w-8 text-[var(--iris-text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <p className="font-mono text-[11px] text-[var(--iris-text-muted)]">选择一个文件查看内容</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
