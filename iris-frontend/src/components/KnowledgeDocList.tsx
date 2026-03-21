"use client";

import type { KnowledgeDocument } from "@/types/knowledge";

function cleanTitle(raw: string): string {
  let cleaned = raw.replace(/!\[[^\]]*\]\([^)]*\)/g, "").trim();
  cleaned = cleaned.replace(/^#+\s*/, "");
  return cleaned || raw;
}

const DOC_META: Record<
  KnowledgeDocument["doc_type"],
  { badge: string; bg: string; color: string }
> = {
  note: { badge: "N", bg: "var(--cy-s)", color: "var(--cy)" },
  url: { badge: "U", bg: "rgba(37,99,235,0.08)", color: "#2563EB" },
  pdf: { badge: "P", bg: "var(--red-bg)", color: "var(--red)" },
  report: { badge: "R", bg: "var(--ac-s)", color: "var(--ac)" },
};

interface Props {
  docs: KnowledgeDocument[];
  selectedId: string | null;
  onSelect: (docId: string) => void;
  onDelete: (docId: string) => void;
}

export function KnowledgeDocList({ docs, selectedId, onSelect, onDelete }: Props) {
  if (docs.length === 0) {
    return <div className="py-8 text-center text-[13px] text-[var(--t3)]">还没有文档。</div>;
  }

  return (
    <div className="space-y-2">
      {docs.map((doc) => {
        const meta = DOC_META[doc.doc_type];
        const active = selectedId === doc.id;

        return (
          <div
            key={doc.id}
            className="group rounded-lg border transition-all"
            style={{
              borderColor: active ? "var(--ac-m)" : "transparent",
              background: active ? "var(--ac-s)" : "transparent",
            }}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => onSelect(doc.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(doc.id);
                }
              }}
              className="flex w-full items-start gap-3 px-3 py-3 text-left hover:bg-[var(--bg-hover)]"
              style={{ borderRadius: "inherit" }}
            >
              <span
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[12px] font-semibold"
                style={{ background: meta.bg, color: meta.color }}
              >
                {meta.badge}
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-[var(--t1)]">{cleanTitle(doc.title)}</span>
                <span className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[var(--t3)]">
                  {doc.company && <span className="font-mono text-[var(--cy-t)]">{doc.company}</span>}
                  <span>{doc.chunk_count} chunks</span>
                  <span>{new Date(doc.created_at).toLocaleDateString("zh-CN")}</span>
                </span>
              </span>

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  if (window.confirm("确认删除此文档？/ Delete this document?")) {
                    onDelete(doc.id);
                  }
                }}
                className="rounded-md p-1.5 text-[var(--t4)] opacity-0 transition-all hover:bg-white hover:text-[var(--red)] group-hover:opacity-100"
                aria-label="删除文档"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
