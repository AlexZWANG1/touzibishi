"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { PeerComparisonTable } from "./PeerComparisonTable";
import { CompsScatter } from "./CompsScatter";

export function CompsPanel() {
  const panel = useAnalysisStore((s) => s.compsPanel);

  if (panel.loading) {
    return (
      <div className="px-[8px] py-[10px] font-mono text-[11px] text-[var(--iris-text-muted)]">
        加载可比公司数据...
      </div>
    );
  }

  if (panel.peers.length === 0) {
    return (
      <div className="px-[8px] py-[10px] font-mono text-[11px] text-[var(--iris-text-muted)]">
        等待可比公司分析...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[10px] p-[6px]">
      <CompsScatter
        data={panel.scatterData}
        xLabel={panel.scatterXLabel}
        yLabel={panel.scatterYLabel}
      />
      <PeerComparisonTable peers={panel.peers} />
    </div>
  );
}
