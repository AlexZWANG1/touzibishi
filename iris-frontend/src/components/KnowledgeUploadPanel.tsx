"use client";

import { useRef, useState } from "react";

type UploadTab = "file" | "url" | "note";

interface Props {
  uploading: boolean;
  onUploadNote: (title: string, content: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadUrl: (url: string, title?: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadFile: (file: File, title?: string, company?: string, tags?: string[]) => Promise<void>;
}

const TAB_LABELS: Record<UploadTab, string> = {
  note: "Note",
  url: "URL",
  file: "File",
};

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

  async function handleSubmit() {
    const companyValue = company.trim() || undefined;
    try {
      if (tab === "note") {
        if (!title.trim() || !content.trim()) return;
        await onUploadNote(title.trim(), content.trim(), companyValue);
      } else if (tab === "url") {
        if (!url.trim()) return;
        await onUploadUrl(url.trim(), title.trim() || undefined, companyValue);
      } else if (selectedFile) {
        await onUploadFile(selectedFile, title.trim() || undefined, companyValue);
      } else {
        return;
      }
      reset();
    } catch {
      // handled by parent
    }
  }

  const canSubmit =
    !uploading &&
    ((tab === "note" && title.trim() && content.trim()) ||
      (tab === "url" && url.trim()) ||
      (tab === "file" && selectedFile));

  return (
    <div className="space-y-4 rounded-[18px] border border-[var(--b1)] bg-[var(--bg-w)] p-4 shadow-card">
      <div className="flex gap-2">
        {(Object.keys(TAB_LABELS) as UploadTab[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className="rounded-pill px-3 py-1.5 text-[12px] font-medium transition-colors"
            style={{
              background: tab === key ? "var(--ac)" : "var(--bg-2)",
              color: tab === key ? "#ffffff" : "var(--t2)",
            }}
          >
            {TAB_LABELS[key]}
          </button>
        ))}
      </div>

      <div className="grid gap-3">
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="标题 / Title"
          className="h-11 rounded-md border border-[var(--b1)] bg-[var(--bg)] px-4 text-[13px] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
        />

        <input
          type="text"
          value={company}
          onChange={(event) => setCompany(event.target.value)}
          placeholder="公司 / Ticker"
          className="h-11 rounded-md border border-[var(--b1)] bg-[var(--bg)] px-4 font-mono text-[13px] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
        />

        {tab === "note" && (
          <textarea
            rows={6}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="输入笔记内容..."
            className="min-h-[140px] rounded-md border border-[var(--b1)] bg-[var(--bg)] px-4 py-3 text-[13px] leading-[1.7] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
          />
        )}

        {tab === "url" && (
          <input
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://..."
            className="h-11 rounded-md border border-[var(--b1)] bg-[var(--bg)] px-4 font-mono text-[13px] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
          />
        )}

        {tab === "file" && (
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileRef.current?.click();
              }
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const file = event.dataTransfer.files[0];
              if (file) setSelectedFile(file);
            }}
            className="rounded-lg border border-dashed border-[var(--b2)] bg-[var(--bg)] px-4 py-8 text-center transition-colors hover:border-[var(--ac)]"
          >
            <div className="text-[13px] font-medium text-[var(--t1)]">
              {selectedFile ? selectedFile.name : "拖拽文件到这里，或点击选择"}
            </div>
            <div className="mt-2 text-[12px] text-[var(--t3)]">支持 PDF、TXT、MD、CSV、JSON</div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md,.csv,.json"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) setSelectedFile(file);
              }}
              className="hidden"
            />
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={!canSubmit}
        className="w-full rounded-[14px] bg-[var(--ac)] px-4 py-3 text-[13px] font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
      >
        {uploading ? "Uploading..." : "Save to Knowledge"}
      </button>
    </div>
  );
}
