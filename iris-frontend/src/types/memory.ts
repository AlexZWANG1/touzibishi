/**
 * Backend GET /api/memory returns a flat dict of memory types → file lists.
 */
export interface MemoryTree {
  companies: string[];
  sectors: string[];
  patterns: string[];
  calibration: string[];
}

export type MemoryType = keyof MemoryTree;

/**
 * Backend GET /api/memory/{type}/{filename} returns { content, path }.
 */
export interface MemoryFileContent {
  content: string;
  path: string;
}

export type MemoryViewMode = "render" | "raw" | "edit";
