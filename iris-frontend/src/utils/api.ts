import type {
  AnalysisStartRequest,
  AnalysisStartResponse,
  SteeringRequest,
  InputResponseRequest,
} from "@/types/api";
import type { WatchlistItem } from "@/types/analysis";
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
