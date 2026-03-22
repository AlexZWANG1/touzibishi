"use client";

import { useRef, useState, useCallback } from "react";

interface Props {
  uploading: boolean;
  onUploadNote: (title: string, content: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadUrl: (url: string, title?: string, company?: string, tags?: string[]) => Promise<void>;
  onUploadFile: (file: File, title?: string, company?: string, tags?: string[]) => Promise<void>;
}

interface PendingFile {
  file: File;
  id: string;
  status: "pending" | "uploading" | "done" | "error";
}

export function KnowledgeUploadPanel({ uploading, onUploadNote, onUploadUrl, onUploadFile }: Props) {
  // --- Note fields ---
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [noteCompany, setNoteCompany] = useState("");

  // --- URL fields ---
  const [urlText, setUrlText] = useState("");
  const [urlCompany, setUrlCompany] = useState("");

  // --- File fields ---
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [fileCompany, setFileCompany] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  // --- Submission states ---
  const [noteUploading, setNoteUploading] = useState(false);
  const [urlUploading, setUrlUploading] = useState(false);
  const [fileUploading, setFileUploading] = useState(false);

  const addFiles = useCallback((files: FileList | File[]) => {
    const newFiles: PendingFile[] = Array.from(files)
      .filter((f) => /\.(pdf|txt|md|csv|json)$/i.test(f.name))
      .map((f) => ({ file: f, id: `${f.name}-${Date.now()}-${Math.random()}`, status: "pending" as const }));
    if (newFiles.length > 0) {
      setPendingFiles((prev) => [...prev, ...newFiles]);
    }
  }, []);

  const removeFile = useCallback((id: string) => {
    setPendingFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  // --- Note submit ---
  async function handleNoteSubmit() {
    if (!noteTitle.trim() || !noteContent.trim() || noteUploading) return;
    setNoteUploading(true);
    try {
      await onUploadNote(noteTitle.trim(), noteContent.trim(), noteCompany.trim() || undefined);
      setNoteTitle("");
      setNoteContent("");
      setNoteCompany("");
    } catch { /* handled by parent */ }
    setNoteUploading(false);
  }

  // --- URL submit (supports multiple URLs, one per line) ---
  async function handleUrlSubmit() {
    const urls = urlText
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.startsWith("http"));
    if (urls.length === 0 || urlUploading) return;
    setUrlUploading(true);
    const company = urlCompany.trim() || undefined;
    for (const u of urls) {
      try {
        await onUploadUrl(u, undefined, company);
      } catch { /* continue */ }
    }
    setUrlText("");
    setUrlCompany("");
    setUrlUploading(false);
  }

  // --- File submit (batch) ---
  async function handleFileSubmit() {
    const toUpload = pendingFiles.filter((f) => f.status === "pending");
    if (toUpload.length === 0 || fileUploading) return;
    setFileUploading(true);
    const company = fileCompany.trim() || undefined;

    for (const pf of toUpload) {
      setPendingFiles((prev) =>
        prev.map((f) => (f.id === pf.id ? { ...f, status: "uploading" as const } : f))
      );
      try {
        await onUploadFile(pf.file, undefined, company);
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pf.id ? { ...f, status: "done" as const } : f))
        );
      } catch {
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pf.id ? { ...f, status: "error" as const } : f))
        );
      }
    }

    // Remove completed files after a short delay
    setTimeout(() => {
      setPendingFiles((prev) => prev.filter((f) => f.status !== "done"));
    }, 1500);
    setFileCompany("");
    setFileUploading(false);
  }

  const inputClass =
    "h-10 rounded-md border border-[var(--b1)] bg-[var(--bg)] px-3 text-[13px] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]";

  return (
    <div className="space-y-5">
      {/* ───── Files: drop zone + batch upload ───── */}
      <section>
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
          上传文件
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => fileRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-5 text-center transition-colors ${
            dragOver
              ? "border-[var(--ac)] bg-[var(--ac-s)]"
              : "border-[var(--b2)] bg-[var(--bg)] hover:border-[var(--ac)]"
          }`}
        >
          <div className="text-[13px] text-[var(--t2)]">
            拖拽文件到这里，或<span className="font-medium text-[var(--ac)]">点击选择</span>
          </div>
          <div className="mt-1 text-[11px] text-[var(--t4)]">PDF / TXT / MD / CSV / JSON · 支持多文件</div>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.csv,.json"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = "";
            }}
            className="hidden"
          />
        </div>

        {pendingFiles.length > 0 && (
          <div className="mt-2 space-y-1">
            {pendingFiles.map((pf) => (
              <div
                key={pf.id}
                className="flex items-center gap-2 rounded-md bg-[var(--bg)] px-3 py-2 text-[12px]"
              >
                <span className="min-w-0 flex-1 truncate font-mono text-[var(--t2)]">{pf.file.name}</span>
                <span className="shrink-0 text-[11px] text-[var(--t4)]">
                  {pf.status === "uploading" ? "上传中..." : pf.status === "done" ? "✓" : pf.status === "error" ? "失败" : `${(pf.file.size / 1024).toFixed(0)}KB`}
                </span>
                {pf.status === "pending" && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeFile(pf.id); }}
                    className="shrink-0 text-[var(--t4)] transition-colors hover:text-[var(--red)]"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
            <div className="mt-2 flex gap-2">
              <input
                type="text"
                value={fileCompany}
                onChange={(e) => setFileCompany(e.target.value)}
                placeholder="公司 / Ticker（可选）"
                className={`${inputClass} flex-1`}
              />
              <button
                type="button"
                onClick={() => void handleFileSubmit()}
                disabled={fileUploading || pendingFiles.every((f) => f.status !== "pending")}
                className="shrink-0 rounded-md bg-[var(--ac)] px-4 py-2 text-[12px] font-semibold text-white transition-opacity disabled:opacity-40"
              >
                {fileUploading ? "上传中..." : `上传 ${pendingFiles.filter((f) => f.status === "pending").length} 个文件`}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ───── URLs: multi-line input ───── */}
      <section>
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
          抓取网页
        </div>
        <textarea
          rows={2}
          value={urlText}
          onChange={(e) => setUrlText(e.target.value)}
          placeholder={"粘贴 URL，每行一个\nhttps://example.com/article"}
          className="w-full rounded-md border border-[var(--b1)] bg-[var(--bg)] px-3 py-2.5 font-mono text-[12px] leading-[1.8] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
        />
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={urlCompany}
            onChange={(e) => setUrlCompany(e.target.value)}
            placeholder="公司 / Ticker（可选）"
            className={`${inputClass} flex-1`}
          />
          <button
            type="button"
            onClick={() => void handleUrlSubmit()}
            disabled={urlUploading || !urlText.trim().startsWith("http")}
            className="shrink-0 rounded-md bg-[var(--ac)] px-4 py-2 text-[12px] font-semibold text-white transition-opacity disabled:opacity-40"
          >
            {urlUploading ? "抓取中..." : "抓取"}
          </button>
        </div>
      </section>

      {/* ───── Note: quick note ───── */}
      <details className="group">
        <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)] transition-colors hover:text-[var(--t2)] [&::-webkit-details-marker]:hidden list-none">
          <span className="inline-flex items-center gap-2">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="transition-transform group-open:rotate-90">
              <path d="M9 5l7 7-7 7" />
            </svg>
            添加笔记
          </span>
        </summary>
        <div className="mt-3 space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder="标题"
              className={`${inputClass} flex-1`}
            />
            <input
              type="text"
              value={noteCompany}
              onChange={(e) => setNoteCompany(e.target.value)}
              placeholder="Ticker"
              className={`${inputClass} w-24`}
            />
          </div>
          <textarea
            rows={4}
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            placeholder="笔记内容..."
            className="w-full rounded-md border border-[var(--b1)] bg-[var(--bg)] px-3 py-2.5 text-[13px] leading-[1.7] text-[var(--t1)] outline-none transition-colors placeholder:text-[var(--t4)] focus:border-[var(--ac)]"
          />
          <button
            type="button"
            onClick={() => void handleNoteSubmit()}
            disabled={noteUploading || !noteTitle.trim() || !noteContent.trim()}
            className="w-full rounded-md bg-[var(--ac)] px-4 py-2.5 text-[12px] font-semibold text-white transition-opacity disabled:opacity-40"
          >
            {noteUploading ? "保存中..." : "保存笔记"}
          </button>
        </div>
      </details>
    </div>
  );
}
