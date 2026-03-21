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
    return <div className="px-6 py-8 text-[13px] text-[var(--t3)]">等待可比公司分析结果...</div>;
  }

  return (
    <div className="space-y-5 p-5 sm:p-6">
      <CompsScatter data={panel.scatterData} xLabel={panel.scatterXLabel} yLabel={panel.scatterYLabel} />
      <PeerComparisonTable peers={panel.peers} />
    </div>
  );
}
