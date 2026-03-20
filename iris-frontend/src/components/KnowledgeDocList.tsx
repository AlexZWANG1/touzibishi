"use client";

import type { KnowledgeDocument } from "@/types/knowledge";

const DOC_TYPE_LABELS: Record<string, string> = {
  note: "NOTE",
  report: "RPT",
  url: "URL",
  pdf: "PDF",
};

interface Props {
  docs: KnowledgeDocument[];
  selectedId: string | null;
  onSelect: (docId: string) => void;
  onDelete: (docId: string) => void;
}

export function KnowledgeDocList({ docs, selectedId, onSelect, onDelete }: Props) {
  if (docs.length === 0) {
    return (
      <div className="py-4 text-center font-mono text-[11px] text-[var(--iris-text-muted)]">
        NO DOCUMENTS
      </div>
    );
  }

  // Group by doc_type
  const grouped: Record<string, KnowledgeDocument[]> = {};
  for (const doc of docs) {
    const key = doc.doc_type;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(doc);
  }

  return (
    <div className="space-y-[6px]">
      {Object.entries(grouped).map(([docType, items]) => (
        <div key={docType}>
          <div className="mb-[2px] flex items-center gap-[6px] px-[4px]">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--iris-accent)]">
              {DOC_TYPE_LABELS[docType] || docType}
            </span>
            <span className="font-mono text-[10px] text-[var(--iris-text-muted)]">
              {items.length}
            </span>
          </div>
          <div>
            {items.map((doc) => (
              <div
                key={doc.id}
                onClick={() => onSelect(doc.id)}
                className={`group flex cursor-pointer items-center justify-between px-[6px] py-[4px] transition-colors ${
                  selectedId === doc.id
                    ? "border-l-2 border-[var(--iris-accent)] bg-[var(--iris-accent)]/5"
                    : "border-l-2 border-transparent hover:bg-[var(--iris-surface-hover)]"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-[11px] text-[var(--iris-text)]">
                    {doc.title}
                  </div>
                  <div className="flex items-center gap-[6px] font-mono text-[10px] text-[var(--iris-text-muted)]">
                    {doc.company && (
                      <span className="text-[var(--iris-data)]">{doc.company}</span>
                    )}
                    <span>{doc.chunk_count}ch</span>
                    <span>
                      {new Date(doc.created_at).toLocaleDateString("zh-CN")}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm("确认删除此文档？/ Delete this document?")) {
                      onDelete(doc.id);
                    }
                  }}
                  className="ml-[4px] p-[2px] text-[var(--iris-text-muted)] opacity-0 transition-all hover:text-red-400 group-hover:opacity-100"
                  title="Delete / 删除"
                  aria-label="Delete document"
                >
                  <svg
                    className="h-[10px] w-[10px]"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
