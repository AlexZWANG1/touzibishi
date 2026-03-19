"use client";

import type { KnowledgeDocument } from "@/types/knowledge";

const DOC_TYPE_LABELS: Record<string, string> = {
  note: "笔记",
  report: "报告",
  url: "网页",
  pdf: "PDF",
};

const DOC_TYPE_COLORS: Record<string, string> = {
  note: "bg-blue-500/20 text-blue-400",
  report: "bg-green-500/20 text-green-400",
  url: "bg-purple-500/20 text-purple-400",
  pdf: "bg-orange-500/20 text-orange-400",
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
      <div className="py-8 text-center text-xs text-[var(--iris-text-muted)]">
        还没有上传任何文档
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
    <div className="space-y-3">
      {Object.entries(grouped).map(([docType, items]) => (
        <div key={docType}>
          <div className="mb-1 flex items-center gap-1.5 px-1">
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                DOC_TYPE_COLORS[docType] || "bg-gray-500/20 text-gray-400"
              }`}
            >
              {DOC_TYPE_LABELS[docType] || docType}
            </span>
            <span className="text-[10px] text-[var(--iris-text-muted)]">
              {items.length}
            </span>
          </div>
          <div className="space-y-0.5">
            {items.map((doc) => (
              <div
                key={doc.id}
                onClick={() => onSelect(doc.id)}
                className={`group flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 transition-colors ${
                  selectedId === doc.id
                    ? "bg-[var(--iris-accent)]/10 text-[var(--iris-accent)]"
                    : "hover:bg-[var(--iris-surface-hover)]"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[11px] font-medium">
                    {doc.title}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-[var(--iris-text-muted)]">
                    {doc.company && (
                      <span className="font-mono">{doc.company}</span>
                    )}
                    <span>{doc.chunk_count} chunks</span>
                    <span>
                      {new Date(doc.created_at).toLocaleDateString("zh-CN")}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(doc.id);
                  }}
                  className="ml-2 rounded p-1 text-[var(--iris-text-muted)] opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
                  title="删除"
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
