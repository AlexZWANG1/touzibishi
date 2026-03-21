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

export function MemoryFileTree({ tree, selectedType, selectedFilename, onSelect }: MemoryFileTreeProps) {
  return (
    <div className="space-y-2">
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

function FolderNode({
  type,
  label,
  files,
  selectedType,
  selectedFilename,
  onSelect,
}: {
  type: MemoryType;
  label: string;
  files: string[];
  selectedType: MemoryType | null;
  selectedFilename: string | null;
  onSelect: (memoryType: MemoryType, filename: string) => void;
}) {
  const [expanded, setExpanded] = useState(files.length > 0);

  return (
    <div className="rounded-lg border border-transparent bg-[rgba(255,255,255,0.35)]">
      <button
        type="button"
        onClick={() => setExpanded((open) => !open)}
        className="flex w-full items-center gap-3 px-3 py-3 text-left"
      >
        <span
          className="inline-block text-[10px] text-[var(--t4)] transition-transform"
          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
        >
          ▶
        </span>
        <span className="font-mono text-[12px] font-semibold text-[var(--ac)]">{label}</span>
        <span className="font-mono text-[11px] text-[var(--t4)]">{files.length}</span>
      </button>

      {expanded && files.length > 0 && (
        <div className="space-y-1 px-2 pb-2">
          {files.map((filename) => {
            const active = selectedType === type && selectedFilename === filename;
            return (
              <button
                key={filename}
                type="button"
                onClick={() => onSelect(type, filename)}
                className="flex w-full items-center rounded-md px-3 py-2 text-left transition-colors"
                style={{
                  background: active ? "var(--bg-w)" : "transparent",
                  color: active ? "var(--ac)" : "var(--t2)",
                  boxShadow: active ? "var(--sh)" : "none",
                }}
              >
                <span className="truncate font-mono text-[12px]">{filename}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
