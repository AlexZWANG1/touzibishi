"use client";

import { useKnowledgeApi } from "@/hooks/useKnowledgeApi";
import { KnowledgeUploadPanel } from "@/components/KnowledgeUploadPanel";
import { KnowledgeDocList } from "@/components/KnowledgeDocList";

export default function KnowledgePage() {
  const {
    docs,
    selectedDoc,
    loading,
    uploading,
    error,
    fetchDocs,
    selectDoc,
    uploadNote,
    uploadUrl,
    uploadFile,
    deleteDoc,
  } = useKnowledgeApi();

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <div className="flex w-72 flex-shrink-0 flex-col border-r border-[var(--iris-border)] bg-[var(--iris-surface)]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--iris-border)] px-4 py-3">
          <h2 className="text-sm font-semibold">知识库</h2>
          <button
            onClick={fetchDocs}
            className="rounded-md p-1.5 text-[var(--iris-text-muted)] transition-colors hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text-secondary)]"
            title="刷新"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        </div>

        {/* Upload panel */}
        <div className="border-b border-[var(--iris-border)] p-3">
          <KnowledgeUploadPanel
            uploading={uploading}
            onUploadNote={uploadNote}
            onUploadUrl={uploadUrl}
            onUploadFile={uploadFile}
          />
        </div>

        {/* Document list */}
        <div
          className="overflow-y-auto p-3"
          style={{ height: "calc(100% - 49px)" }}
        >
          {loading && docs.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--iris-accent)] border-t-transparent" />
            </div>
          ) : (
            <KnowledgeDocList
              docs={docs}
              selectedId={selectedDoc?.id ?? null}
              onSelect={selectDoc}
              onDelete={deleteDoc}
            />
          )}
        </div>
      </div>

      {/* Main content — document viewer */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="m-4 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {selectedDoc ? (
          <div className="p-6">
            {/* Document header */}
            <div className="mb-4 border-b border-[var(--iris-border)] pb-4">
              <h1 className="text-lg font-semibold">{selectedDoc.title}</h1>
              <div className="mt-1 flex items-center gap-3 text-[11px] text-[var(--iris-text-muted)]">
                <span className="rounded bg-[var(--iris-surface)] px-1.5 py-0.5 font-medium">
                  {selectedDoc.doc_type.toUpperCase()}
                </span>
                {selectedDoc.company && (
                  <span className="font-mono">{selectedDoc.company}</span>
                )}
                <span>{selectedDoc.chunk_count} chunks</span>
                {selectedDoc.source_path && (
                  <span className="truncate" title={selectedDoc.source_path}>
                    {selectedDoc.source_path}
                  </span>
                )}
                <span>
                  {new Date(selectedDoc.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
              {selectedDoc.tags && selectedDoc.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {selectedDoc.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-[var(--iris-accent)]/10 px-2 py-0.5 text-[10px] text-[var(--iris-accent)]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Document content */}
            <div className="whitespace-pre-wrap text-xs leading-relaxed text-[var(--iris-text-secondary)]">
              {selectedDoc.content_text || (
                <span className="italic text-[var(--iris-text-muted)]">
                  内容加载中...
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <svg
                className="mx-auto mb-3 h-12 w-12 text-[var(--iris-text-muted)]"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
              <p className="text-[var(--iris-text-muted)]">
                上传研报、笔记或文章到知识库
              </p>
              <p className="mt-1 text-[10px] text-[var(--iris-text-muted)]">
                AI 分析时会自动检索相关内容
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
