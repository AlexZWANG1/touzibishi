import type {
  AnalysisStartRequest,
  AnalysisStartResponse,
  SteeringRequest,
  InputResponseRequest,
} from "@/types/api";
import type { WatchlistItem, HistoryListResponse, AnalysisSnapshot } from "@/types/analysis";
import type { MemoryTree, MemoryFileContent } from "@/types/memory";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export async function startAnalysis(
  data: AnalysisStartRequest
): Promise<AnalysisStartResponse> {
  return request<AnalysisStartResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function sendSteering(
  analysisId: string,
  data: SteeringRequest
): Promise<void> {
  await request(`/api/analyze/${analysisId}/steer`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function respondToInput(
  analysisId: string,
  data: InputResponseRequest
): Promise<void> {
  await request(`/api/analyze/${analysisId}/respond`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  return request<WatchlistItem[]>("/api/watchlist");
}

/**
 * GET /api/memory → { companies: [...], sectors: [...], patterns: [...], calibration: [...] }
 */
export async function getMemoryTree(): Promise<MemoryTree> {
  return request<MemoryTree>("/api/memory");
}

/**
 * GET /api/memory/{type}/{filename}
 */
export async function getMemoryFile(
  memoryType: string,
  filename: string
): Promise<MemoryFileContent> {
  return request<MemoryFileContent>(
    `/api/memory/${encodeURIComponent(memoryType)}/${encodeURIComponent(filename)}`
  );
}

/**
 * PUT /api/memory/{type}/{filename}
 */
export async function updateMemoryFile(
  memoryType: string,
  filename: string,
  content: string
): Promise<void> {
  await request(`/api/memory/${encodeURIComponent(memoryType)}/${encodeURIComponent(filename)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

/**
 * DELETE /api/memory/{type}/{filename}
 */
export async function deleteMemoryFile(
  memoryType: string,
  filename: string
): Promise<void> {
  await request(`/api/memory/${encodeURIComponent(memoryType)}/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
}

export function createAnalysisEventSource(analysisId: string): EventSource {
  return new EventSource(`${BASE_URL}/api/analyze/${analysisId}/stream`);
}

export async function getHistory(
  ticker?: string, limit = 30, offset = 0
): Promise<HistoryListResponse> {
  const params = new URLSearchParams();
  if (ticker) params.set("ticker", ticker);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request<HistoryListResponse>(`/api/history?${params}`);
}

export async function getHistoryDetail(runId: string): Promise<AnalysisSnapshot> {
  return request<AnalysisSnapshot>(`/api/history/${encodeURIComponent(runId)}`);
}

export async function continueAnalysis(
  analysisId: string,
  message: string
): Promise<{ status: string; turn: number }> {
  return request(`/api/analyze/${encodeURIComponent(analysisId)}/continue`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function probeSession(analysisId: string): Promise<{ live: boolean; query?: string }> {
  try {
    const res = await fetch(`${BASE_URL}/api/analyze/${analysisId}/status`);
    if (res.status !== 200) return { live: false };
    const data = await res.json();
    const live = data.exists === true && (data.status === "running" || data.status === "waiting");
    return { live, query: data.query || "" };
  } catch {
    return { live: false };
  }
}

// ── Knowledge API ─────────────────────────────────────────

import type {
  KnowledgeDocument,
  KnowledgeSearchResponse,
} from "@/types/knowledge";

export async function getKnowledgeDocs(
  company?: string,
  docType?: string
): Promise<KnowledgeDocument[]> {
  const params = new URLSearchParams();
  if (company) params.set("company", company);
  if (docType) params.set("doc_type", docType);
  const qs = params.toString();
  return request<KnowledgeDocument[]>(`/api/knowledge${qs ? `?${qs}` : ""}`);
}

export async function getKnowledgeDoc(
  docId: string
): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>(
    `/api/knowledge/${encodeURIComponent(docId)}`
  );
}

export async function uploadKnowledgeNote(data: {
  title: string;
  content: string;
  company?: string;
  tags?: string[];
}): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>("/api/knowledge/upload-note", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadKnowledgeUrl(data: {
  url: string;
  title?: string;
  company?: string;
  tags?: string[];
}): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>("/api/knowledge/upload-url", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadKnowledgeFile(
  file: File,
  opts?: { title?: string; company?: string; tags?: string[] }
): Promise<KnowledgeDocument> {
  const formData = new FormData();
  formData.append("file", file);
  if (opts?.title) formData.append("title", opts.title);
  if (opts?.company) formData.append("company", opts.company);
  if (opts?.tags) formData.append("tags", JSON.stringify(opts.tags));

  const res = await fetch(`${BASE_URL}/api/knowledge/upload-file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteKnowledgeDoc(docId: string): Promise<void> {
  await request(`/api/knowledge/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
}

export async function searchKnowledge(
  query: string,
  topK?: number,
  company?: string
): Promise<KnowledgeSearchResponse> {
  return request<KnowledgeSearchResponse>("/api/knowledge/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK, company }),
  });
}
