"use client";

import { useState } from "react";
import type { MemoryTree, MemoryType } from "@/types/memory";

interface MemoryFileTreeProps {
  tree: MemoryTree;
  selectedType: MemoryType | null;
  selectedFilename: string | null;
  onSelect: (memoryType: MemoryType, filename: string) => void;
}

const TYPE_LABELS: Record<MemoryType, string> = {
  companies: "公司",
  sectors: "行业",
  patterns: "模式",
  calibration: "校准",
};

export function MemoryFileTree({
  tree,
  selectedType,
  selectedFilename,
  onSelect,
}: MemoryFileTreeProps) {
  return (
    <div className="space-y-1">
      {(Object.keys(TYPE_LABELS) as MemoryType[]).map((type) => (
        <FolderNode
          key={type}
          type={type}
          label={TYPE_LABELS[type]}
          files={tree[type]}
          selectedType={selectedType}
          selectedFilename={selectedFilename}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

interface FolderNodeProps {
  type: MemoryType;
  label: string;
  files: string[];
  selectedType: MemoryType | null;
  selectedFilename: string | null;
  onSelect: (memoryType: MemoryType, filename: string) => void;
}

function FolderNode({
  type,
  label,
  files,
  selectedType,
  selectedFilename,
  onSelect,
}: FolderNodeProps) {
  const [expanded, setExpanded] = useState(files.length > 0);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm text-[var(--iris-text-secondary)] transition-colors hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text)]"
      >
        <svg
          className={`h-3.5 w-3.5 flex-shrink-0 transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <svg
          className="h-4 w-4 flex-shrink-0 text-amber-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
          />
        </svg>
        <span className="truncate">
          {label} ({files.length})
        </span>
      </button>
      {expanded && files.length > 0 && (
        <div className="ml-4 space-y-0.5">
          {files.map((filename) => {
            const isSelected = selectedType === type && selectedFilename === filename;
            return (
              <button
                key={filename}
                onClick={() => onSelect(type, filename)}
                className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                  isSelected
                    ? "bg-[var(--iris-accent)]/10 text-[var(--iris-accent)]"
                    : "text-[var(--iris-text-secondary)] hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text)]"
                }`}
              >
                <span className="w-3.5" />
                <svg
                  className="h-4 w-4 flex-shrink-0 text-[var(--iris-text-muted)]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="truncate">{filename}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
