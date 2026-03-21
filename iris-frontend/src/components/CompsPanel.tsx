"use client";

import { useAnalysisStore } from "@/hooks/useAnalysisStore";
import { PeerComparisonTable } from "./PeerComparisonTable";
import { CompsScatter } from "./CompsScatter";

export function CompsPanel() {
  const panel = useAnalysisStore((s) => s.compsPanel);

  if (panel.loading) {
    return <div className="px-6 py-8 text-[13px] text-[var(--t3)]">加载可比公司数据...</div>;
  }

  if (panel.peers.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t4)]">可比公司</div>
        <p className="mt-2 text-[13px] text-[var(--t3)]">可比公司分析完成后，散点图和同业对比表会展示在这里。</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      <CompsScatter data={panel.scatterData} xLabel={panel.scatterXLabel} yLabel={panel.scatterYLabel} />
      <PeerComparisonTable peers={panel.peers} />
    </div>
  );
}
