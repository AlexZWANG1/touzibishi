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
    { key: "note", label: "NOTE" },
    { key: "url", label: "URL" },
    { key: "file", label: "FILE" },
  ];

  const canSubmit =
    !uploading &&
    ((tab === "note" && title.trim() && content.trim()) ||
      (tab === "url" && url.trim()) ||
      (tab === "file" && selectedFile));

  return (
    <div className="border border-[var(--iris-border)] bg-[var(--iris-surface)] p-[6px]">
      {/* Tab bar */}
      <div className="mb-[4px] flex border border-[var(--iris-border)] bg-[var(--iris-bg)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-[6px] py-[3px] font-mono text-[10px] uppercase tracking-wider transition-colors ${
              tab === t.key
                ? "bg-[var(--iris-accent)] text-white"
                : "text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Common fields */}
      <div className="mb-[4px] flex gap-[4px]">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题"
          className="h-[28px] flex-1 border border-[var(--iris-border)] bg-[var(--iris-bg)] px-[6px] font-mono text-[11px] text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
        />
        <input
          type="text"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="股票"
          className="h-[28px] w-[72px] border border-[var(--iris-border)] bg-[var(--iris-bg)] px-[6px] font-mono text-[11px] text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
        />
      </div>

      {/* Tab-specific content */}
      {tab === "note" && (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="输入笔记内容..."
          rows={4}
          className="mb-[4px] w-full border border-[var(--iris-border)] bg-[var(--iris-bg)] px-[6px] py-[4px] font-mono text-[11px] text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
        />
      )}

      {tab === "url" && (
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          className="mb-[4px] h-[28px] w-full border border-[var(--iris-border)] bg-[var(--iris-bg)] px-[6px] font-mono text-[11px] text-[var(--iris-text)] placeholder:text-[var(--iris-text-muted)] focus:border-[var(--iris-accent)] focus:outline-none"
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
          className="mb-[4px] flex cursor-pointer items-center justify-center border border-dashed border-[var(--iris-border)] bg-[var(--iris-bg)] py-[12px] font-mono text-[11px] text-[var(--iris-text-muted)] transition-colors hover:border-[var(--iris-accent)]"
        >
          {selectedFile ? (
            <span className="text-[var(--iris-text)]">{selectedFile.name}</span>
          ) : (
            <span>DROP FILE // PDF, TXT, MD</span>
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
        className="w-full bg-[var(--iris-accent)] px-[8px] py-[4px] font-mono text-[11px] font-medium uppercase tracking-wider text-white transition-opacity disabled:opacity-30"
      >
        {uploading ? "UPLOADING..." : "SAVE"}
      </button>
    </div>
  );
}
