"use client";

import { useMemo, useState } from "react";
import type { KnowledgeDocument, DocCategory } from "@/types/knowledge";

function cleanTitle(raw: string): string {
  let cleaned = raw.replace(/!\[[^\]]*\]\([^)]*\)/g, "").trim();
  cleaned = cleaned.replace(/^#+\s*/, "");
  return cleaned || raw;
}

const CATEGORY_META: Record<DocCategory, { label: string; badge: string; bg: string; color: string }> = {
  research:  { label: "研报", badge: "研", bg: "var(--ac-s)",              color: "var(--ac)" },
  interview: { label: "访谈", badge: "访", bg: "var(--cy-s)",              color: "var(--cy)" },
  paper:     { label: "论文", badge: "论", bg: "rgba(37,99,235,0.08)",     color: "#2563EB" },
  note:      { label: "笔记", badge: "记", bg: "var(--amber-bg)",          color: "var(--amber)" },
  other:     { label: "其他", badge: "他", bg: "var(--bg-2)",              color: "var(--t3)" },
};

const ALL_CATEGORIES: DocCategory[] = ["research", "interview", "paper", "note", "other"];

interface Props {
  docs: KnowledgeDocument[];
  selectedId: string | null;
  onSelect: (docId: string) => void;
  onDelete: (docId: string) => void;
}

export function KnowledgeDocList({ docs, selectedId, onSelect, onDelete }: Props) {
  const [activeCategory, setActiveCategory] = useState<DocCategory | "all">("all");
  const [activeIndustry, setActiveIndustry] = useState<string | "all">("all");

  // Collect unique industries from docs
  const industries = useMemo(() => {
    const set = new Set<string>();
    for (const doc of docs) {
      if (doc.industry) set.add(doc.industry);
    }
    return Array.from(set).sort();
  }, [docs]);

  // Filter docs
  const filtered = useMemo(() => {
    return docs.filter((doc) => {
      if (activeCategory !== "all" && (doc.category || "other") !== activeCategory) return false;
      if (activeIndustry !== "all" && doc.industry !== activeIndustry) return false;
      return true;
    });
  }, [docs, activeCategory, activeIndustry]);

  if (docs.length === 0) {
    return <div className="py-8 text-center text-[13px] text-[var(--t3)]">还没有文档。</div>;
  }

  return (
    <div className="space-y-3">
      {/* Category filter */}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setActiveCategory("all")}
          className="rounded-pill px-2.5 py-1 text-[11px] font-medium transition-colors"
          style={{
            background: activeCategory === "all" ? "var(--ac)" : "var(--bg-2)",
            color: activeCategory === "all" ? "#fff" : "var(--t2)",
          }}
        >
          全部 {docs.length}
        </button>
        {ALL_CATEGORIES.map((cat) => {
          const count = docs.filter((d) => (d.category || "other") === cat).length;
          if (count === 0) return null;
          const meta = CATEGORY_META[cat];
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(activeCategory === cat ? "all" : cat)}
              className="rounded-pill px-2.5 py-1 text-[11px] font-medium transition-colors"
              style={{
                background: activeCategory === cat ? meta.color : "var(--bg-2)",
                color: activeCategory === cat ? "#fff" : "var(--t2)",
              }}
            >
              {meta.label} {count}
            </button>
          );
        })}
      </div>

      {/* Industry filter (only show if there are industries) */}
      {industries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {industries.map((ind) => (
            <button
              key={ind}
              type="button"
              onClick={() => setActiveIndustry(activeIndustry === ind ? "all" : ind)}
              className="rounded-pill px-2.5 py-1 text-[11px] font-medium transition-colors"
              style={{
                background: activeIndustry === ind ? "var(--cy)" : "var(--bg-2)",
                color: activeIndustry === ind ? "#fff" : "var(--t3)",
              }}
            >
              {ind}
            </button>
          ))}
        </div>
      )}

      {/* Document list */}
      <div className="space-y-1.5">
        {filtered.map((doc) => {
          const cat = (doc.category || "other") as DocCategory;
          const meta = CATEGORY_META[cat] || CATEGORY_META.other;
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
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(doc.id);
                  }
                }}
                className="flex w-full items-start gap-3 px-3 py-2.5 text-left hover:bg-[var(--bg-hover)]"
                style={{ borderRadius: "inherit" }}
              >
                <span
                  className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold"
                  style={{ background: meta.bg, color: meta.color }}
                >
                  {meta.badge}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-[var(--t1)]">{cleanTitle(doc.title)}</span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--t3)]">
                    {doc.company && <span className="font-mono text-[var(--cy-t)]">{doc.company}</span>}
                    {doc.industry && (
                      <span className="rounded-pill bg-[var(--bg-2)] px-2 py-0.5 text-[10px]">{doc.industry}</span>
                    )}
                    <span>{doc.chunk_count} chunks</span>
                    <span>{new Date(doc.created_at).toLocaleDateString("zh-CN")}</span>
                  </span>
                </span>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm("确认删除此文档？")) {
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

        {filtered.length === 0 && (
          <div className="py-6 text-center text-[12px] text-[var(--t3)]">
            当前筛选条件下没有文档。
          </div>
        )}
      </div>
    </div>
  );
}
