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
    <div className="flex h-[calc(100vh-56px)] bg-[var(--bg)]">
      <aside className="flex w-[280px] shrink-0 flex-col border-r border-[var(--b2)] bg-[var(--bg-2)]">
        <div className="border-b border-[var(--b1)] px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Memory Manager
              </div>
              <div className="mt-1 text-[14px] font-medium text-[var(--t1)]">公司、行业、模式与校准文件</div>
            </div>
            <button
              type="button"
              onClick={refreshTree}
              className="rounded-md p-2 text-[var(--t3)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--t1)]"
              aria-label="刷新记忆树"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading && !hasFiles ? (
            <div className="rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg)] px-4 py-8 text-center text-[13px] text-[var(--t3)]">
              正在载入记忆文件...
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
      </aside>

      <section className="min-w-0 flex-1">
        {error && (
          <div className="m-6 rounded-lg border border-[var(--red-bg)] bg-[rgba(185,28,28,0.04)] px-4 py-3 text-[13px] text-[var(--red)]">
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
          <div className="flex h-full items-center justify-center px-8">
            <div className="max-w-[440px] text-center">
              <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-[18px] bg-[var(--ac-s)] text-[var(--ac)]">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <h2 className="mt-5 font-display text-[32px] font-medium text-[var(--ink)]">Memory Files</h2>
              <p className="mt-3 text-[14px] leading-[1.8] text-[var(--t3)]">
                左侧文件树管理的是长期记忆与校准资料。选中任意文件后，你可以在右侧查看渲染效果、源码，或直接编辑。
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
