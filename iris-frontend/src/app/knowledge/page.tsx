"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
    <div className="flex h-[calc(100vh-3.5rem)] bg-[var(--iris-bg)]">
      {/* Sidebar */}
      <div className="flex w-[240px] shrink-0 flex-col border-r border-[var(--iris-border)] bg-[var(--iris-surface)] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--iris-border)] px-[10px] py-[6px]">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--iris-accent)]">
            KNOWLEDGE BASE
          </h2>
          <button
            onClick={fetchDocs}
            className="p-1 text-[var(--iris-text-muted)] transition-colors hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text-secondary)]"
            title="刷新"
          >
            <svg
              className="h-3 w-3"
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
        <div className="border-b border-[var(--iris-border)] p-[6px]">
          <KnowledgeUploadPanel
            uploading={uploading}
            onUploadNote={uploadNote}
            onUploadUrl={uploadUrl}
            onUploadFile={uploadFile}
          />
        </div>

        {/* Document list */}
        <div className="flex-1 min-h-0 overflow-y-auto p-[6px]">
          {loading && docs.length === 0 ? (
            <div className="flex items-center justify-center py-6">
              <div className="h-3 w-3 animate-spin border border-[var(--iris-accent)] border-t-transparent" />
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

      {/* Main content — document reader */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="m-[8px] border border-red-500/20 bg-red-500/5 px-[10px] py-[6px] font-mono text-[11px] text-red-400">
            {error}
          </div>
        )}

        {selectedDoc ? (
          <div className="px-[clamp(24px,4vw,64px)] py-[32px]">
            {/* Document header */}
            <div className="mb-[24px] max-w-[720px] border-b border-[var(--iris-border)] pb-[20px]">
              <h1 className="text-[22px] font-semibold leading-tight text-[var(--iris-text)]">
                {selectedDoc.title}
              </h1>
              <div className="mt-[10px] flex flex-wrap items-center gap-[10px] text-[13px] text-[var(--iris-text-muted)]">
                <span className="rounded-sm border border-[var(--iris-border)] bg-[var(--iris-surface)] px-[6px] py-[2px] font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--iris-accent)]">
                  {selectedDoc.doc_type.toUpperCase()}
                </span>
                {selectedDoc.company && (
                  <span className="font-semibold text-[var(--iris-data)]">{selectedDoc.company}</span>
                )}
                <span className="font-mono text-[12px]">{selectedDoc.chunk_count} chunks</span>
                {selectedDoc.source_path && (
                  <span className="max-w-[240px] truncate font-mono text-[12px]" title={selectedDoc.source_path}>
                    {selectedDoc.source_path}
                  </span>
                )}
                <span className="font-mono text-[12px]">
                  {new Date(selectedDoc.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
              {selectedDoc.tags && selectedDoc.tags.length > 0 && (
                <div className="mt-[8px] flex flex-wrap gap-[6px]">
                  {selectedDoc.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-sm border border-[var(--iris-accent)]/20 bg-[var(--iris-accent)]/5 px-[6px] py-[2px] text-[11px] text-[var(--iris-accent)]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Document content */}
            {selectedDoc.content_text ? (
              <div className="prose-reader">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {selectedDoc.content_text}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="flex items-center gap-[8px] py-[24px] text-[var(--iris-text-muted)]">
                <div className="h-3 w-3 animate-spin border border-[var(--iris-accent)] border-t-transparent" />
                <span className="text-[13px]">Loading...</span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <svg
                className="mx-auto mb-[12px] h-10 w-10 text-[var(--iris-text-muted)]/50"
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
              <p className="text-[14px] text-[var(--iris-text-muted)]">
                上传研报、笔记或文章到知识库
              </p>
              <p className="mt-[4px] text-[12px] text-[var(--iris-text-muted)]/60">
                AI 分析时会自动检索相关内容
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
