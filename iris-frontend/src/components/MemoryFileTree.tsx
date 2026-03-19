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
  companies: "COMPANIES",
  sectors: "SECTORS",
  patterns: "PATTERNS",
  calibration: "CALIBRATION",
};

export function MemoryFileTree({
  tree,
  selectedType,
  selectedFilename,
  onSelect,
}: MemoryFileTreeProps) {
  return (
    <div className="space-y-[2px]">
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
        className="flex w-full items-center gap-[4px] px-[6px] py-[3px] text-left transition-colors hover:bg-[var(--iris-surface-hover)]"
      >
        <svg
          className={`h-[8px] w-[8px] shrink-0 text-[var(--iris-text-muted)] transition-transform ${
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
        <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--iris-accent)]">
          {label}
        </span>
        <span className="font-mono text-[10px] text-[var(--iris-text-muted)]">
          ({files.length})
        </span>
      </button>
      {expanded && files.length > 0 && (
        <div className="ml-[12px]">
          {files.map((filename) => {
            const isSelected = selectedType === type && selectedFilename === filename;
            return (
              <button
                key={filename}
                onClick={() => onSelect(type, filename)}
                className={`flex w-full items-center gap-[4px] px-[6px] py-[2px] text-left font-mono text-[11px] transition-colors ${
                  isSelected
                    ? "bg-[var(--iris-surface-hover)] text-[var(--iris-accent)]"
                    : "text-[var(--iris-text-secondary)] hover:bg-[var(--iris-surface-hover)] hover:text-[var(--iris-text)]"
                }`}
              >
                <span className="truncate">{filename}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
