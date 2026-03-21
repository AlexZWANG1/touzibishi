"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useKnowledgeApi } from "@/hooks/useKnowledgeApi";
import { KnowledgeUploadPanel } from "@/components/KnowledgeUploadPanel";
import { KnowledgeDocList } from "@/components/KnowledgeDocList";

function cleanContentForDisplay(raw: string): string {
  let text = raw;
  const lines = text.split("\n");
  let start = 0;

  for (let index = 0; index < Math.min(lines.length, 10); index += 1) {
    const trimmed = lines[index].trim();
    if (
      trimmed.startsWith("Title:") ||
      trimmed.startsWith("URL Source:") ||
      trimmed.startsWith("Published Time:") ||
      trimmed.startsWith("Markdown Content:")
    ) {
      start = index + 1;
      if (trimmed.startsWith("Markdown Content:")) break;
    } else if (trimmed && index > 0) {
      break;
    }
  }

  if (start > 0) {
    text = lines.slice(start).join("\n").trim();
  }

  return text.replace(
    /!\[(?:Image\s*\d+:\s*)?([^\]]*?)\]\(https?:\/\/s\.w\.org\/images\/core\/emoji\/[^)]+\)/g,
    "$1",
  );
}

function cleanDisplayTitle(raw: string): string {
  return raw.replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/^#+\s*/, "").trim() || raw;
}

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
    <div className="flex h-[calc(100vh-56px)] bg-[var(--bg)]">
      <aside className="flex w-[320px] shrink-0 flex-col border-r border-[var(--b2)] bg-[var(--bg-2)]">
        <div className="border-b border-[var(--b1)] px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                Knowledge Base
              </div>
              <div className="mt-1 text-[14px] font-medium text-[var(--t1)]">研究资料、笔记与外部文档</div>
            </div>
            <button
              type="button"
              onClick={fetchDocs}
              className="rounded-md p-2 text-[var(--t3)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--t1)]"
              aria-label="刷新文档列表"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        <div className="border-b border-[var(--b1)] p-4">
          <KnowledgeUploadPanel
            uploading={uploading}
            onUploadNote={uploadNote}
            onUploadUrl={uploadUrl}
            onUploadFile={uploadFile}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading && docs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg)] px-4 py-8 text-center text-[13px] text-[var(--t3)]">
              正在载入文档列表...
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
      </aside>

      <section className="min-w-0 flex-1 overflow-y-auto">
        {error && (
          <div className="m-6 rounded-lg border border-[var(--red-bg)] bg-[rgba(185,28,28,0.04)] px-4 py-3 text-[13px] text-[var(--red)]">
            {error}
          </div>
        )}

        {selectedDoc ? (
          <div className="px-[clamp(28px,5vw,72px)] py-10">
            <div className="max-w-[820px]">
              <div className="border-b border-[var(--b1)] pb-6">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-md bg-[var(--bg-2)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
                    {selectedDoc.doc_type}
                  </span>
                  {selectedDoc.company && (
                    <span className="font-mono text-[12px] font-semibold text-[var(--cy-t)]">{selectedDoc.company}</span>
                  )}
                  <span className="font-mono text-[12px] text-[var(--t3)]">{selectedDoc.chunk_count} chunks</span>
                  <span className="font-mono text-[12px] text-[var(--t3)]">
                    {new Date(selectedDoc.created_at).toLocaleString("zh-CN")}
                  </span>
                </div>

                <h1 className="mt-5 font-display text-fluid-h1 font-medium leading-[1.08] tracking-[-0.03em] text-[var(--ink)]">
                  {cleanDisplayTitle(selectedDoc.title)}
                </h1>

                {selectedDoc.source_path && (
                  <div className="mt-4 text-[13px] text-[var(--t3)]">
                    来源：
                    {selectedDoc.source_path.startsWith("http") ? (
                      <a
                        href={selectedDoc.source_path}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-1 font-mono text-[12px] text-[var(--ac)] hover:underline"
                      >
                        {(() => {
                          try {
                            return new URL(selectedDoc.source_path).hostname;
                          } catch {
                            return selectedDoc.source_path;
                          }
                        })()}
                      </a>
                    ) : (
                      <span className="ml-1 font-mono text-[12px] text-[var(--t2)]">{selectedDoc.source_path}</span>
                    )}
                  </div>
                )}

                {selectedDoc.tags.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {selectedDoc.tags.map((tag) => (
                      <span key={tag} className="rounded-pill bg-[var(--ac-s)] px-3 py-1 text-[11px] font-medium text-[var(--ac)]">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {selectedDoc.content_text ? (
                <div className="prose-reader mt-8">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      img: ({ node, ...props }) => (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img {...props} alt={props.alt || ""} loading="lazy" />
                      ),
                    }}
                  >
                    {cleanContentForDisplay(selectedDoc.content_text)}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="mt-8 rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg-w)] px-5 py-8 text-[13px] text-[var(--t3)] shadow-card">
                  文档内容载入中...
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-8">
            <div className="max-w-[460px] text-center">
              <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-[18px] bg-[var(--ac-s)] text-[var(--ac)]">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h2 className="mt-5 font-display text-[32px] font-medium text-[var(--ink)]">Knowledge Reader</h2>
              <p className="mt-3 text-[14px] leading-[1.8] text-[var(--t3)]">
                在左侧上传研报、网页或笔记。Prism 会把这些资料纳入研究流程，并在分析时自动检索相关片段。
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
