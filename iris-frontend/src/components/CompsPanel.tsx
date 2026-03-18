"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { PeerComparisonTable } from "./PeerComparisonTable";
import { CompsScatter } from "./CompsScatter";

export function CompsPanel() {
  const panel = useAnalysisStore((s) => s.compsPanel);

  if (panel.loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--phase-evaluate)] border-t-transparent" />
          <p className="text-sm text-[var(--iris-text-muted)]">加载可比公司数据...</p>
        </div>
      </div>
    );
  }

  if (panel.peers.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <svg
            className="mx-auto mb-3 h-10 w-10 text-[var(--iris-text-muted)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <p className="text-sm text-[var(--iris-text-muted)]">
            等待可比公司分析...
          </p>
          <p className="mt-1 text-xs text-[var(--iris-text-muted)]">
            IRIS 将选取合适的同行公司进行对比
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-5">
      <CompsScatter
        data={panel.scatterData}
        xLabel={panel.scatterXLabel}
        yLabel={panel.scatterYLabel}
      />
      <PeerComparisonTable peers={panel.peers} />
    </div>
  );
}
