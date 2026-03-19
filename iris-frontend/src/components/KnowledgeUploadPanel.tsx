"use client";

import { useState, useRef } from "react";

type UploadTab = "file" | "url" | "note";

interface Props {
  uploading: boolean;
  onUploadNote: (title: string, content: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadUrl: (url: string, title?: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadFile: (file: File, title?: string, company?: string, tags?: string[]) => Promise<void>;
}

export function KnowledgeUploadPanel({ uploading, onUploadNote, onUploadUrl, onUploadFile }: Props) {
  const [tab, setTab] = useState<UploadTab>("note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [company, setCompany] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setTitle("");
    setContent("");
    setUrl("");
    setCompany("");
    setSelectedFile(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleSubmit = async () => {
    const comp = company.trim() || undefined;
    try {
      if (tab === "note") {
        if (!title.trim() || !content.trim()) return;
        await onUploadNote(title.trim(), content.trim(), comp);
      } else if (tab === "url") {
        if (!url.trim()) return;
        await onUploadUrl(url.trim(), title.trim() || undefined, comp);
      } else if (tab === "file") {
        if (!selectedFile) return;
        await onUploadFile(selectedFile, title.trim() || undefined, comp);
      }
      reset();
    } catch {
      // Error handled by parent hook
    }
  };

  const tabs: { key: UploadTab; label: string }[] = [
    { key: "note", label: "写笔记" },
    { key: "url", label: "添加链接" },
    { key: "file", label: "上传文件" },
  ];

  const canSubmit =
    !uploading &&
    ((tab === "note" && title.trim() && content.trim()) ||
      (tab === "url" && url.trim()) ||
      (tab === "file" && selectedFile));

  return (
    <div className="rounded-lg border border-[var(--iris-border)] bg-[var(--iris-surface)] p-4">
      {/* Tab bar */}
      <div className="mb-3 flex gap-1 rounded-md bg-[var(--iris-bg)] p-0.5">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-md px-3 py-1.5 text-[11px] font-medium transition-colors ${
              tab === t.key
                ? "bg-[var(--iris-surface)] text-[var(--iris-text)]"
                : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Common fields */}
      <div className="mb-2 flex gap-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题"
          className="flex-1 rounded-md border border-[var(--iris-border)] bg-[var(--iris-bg)] px-3 py-1.5 text-xs text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)]"
        />
        <input
          type="text"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="关联股票 (可选)"
          className="w-32 rounded-md border border-[var(--iris-border)] bg-[var(--iris-bg)] px-3 py-1.5 text-xs text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)]"
        />
      </div>

      {/* Tab-specific content */}
      {tab === "note" && (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="输入笔记内容..."
          rows={6}
          className="mb-2 w-full rounded-md border border-[var(--iris-border)] bg-[var(--iris-bg)] px-3 py-2 text-xs text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)]"
        />
      )}

      {tab === "url" && (
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          className="mb-2 w-full rounded-md border border-[var(--iris-border)] bg-[var(--iris-bg)] px-3 py-1.5 text-xs text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)]"
        />
      )}

      {tab === "file" && (
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) setSelectedFile(f);
          }}
          className="mb-2 flex cursor-pointer items-center justify-center rounded-md border-2 border-dashed border-[var(--iris-border)] bg-[var(--iris-bg)] py-6 text-xs text-[var(--iris-text-muted)] transition-colors hover:border-[var(--iris-accent)]"
        >
          {selectedFile ? (
            <span className="text-[var(--iris-text)]">{selectedFile.name}</span>
          ) : (
            <span>点击或拖拽文件到此处 (PDF, TXT, MD)</span>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md,.csv,.json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setSelectedFile(f);
            }}
            className="hidden"
          />
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="w-full rounded-md bg-[var(--iris-accent)] px-4 py-1.5 text-xs font-medium text-white transition-opacity disabled:opacity-40"
      >
        {uploading ? "上传中..." : "保存到知识库"}
      </button>
    </div>
  );
}
