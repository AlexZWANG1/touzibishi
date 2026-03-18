export type PageState = "IDLE" | "RUNNING" | "WAITING" | "COMPLETE";

export type Phase = "gather" | "analyze" | "evaluate" | "finalize";

export type ActiveTab = "data" | "model" | "comps" | "memory";

export type EventColor = "green" | "blue" | "amber" | "gray" | "purple";

export interface TimelineEvent {
  id: string;
  timestamp: number;
  tool: string;
  message: string;
  phase: Phase;
  color: EventColor;
  duration?: number;
  status: "running" | "complete" | "error";
}

export interface PendingQuestion {
  question: string;
  context: string;
  options: string[];
}

export interface MetricItem {
  label: string;
  value: string | number;
  unit?: string;
  change?: number;
  changeLabel?: string;
}

export interface FinancialRow {
  label: string;
  values: (string | number)[];
  isHeader?: boolean;
  isBold?: boolean;
  indent?: number;
}

export interface FinancialTableData {
  title: string;
  headers: string[];
  rows: FinancialRow[];
}

export interface DataPanelState {
  metrics: MetricItem[];
  financialTables: FinancialTableData[];
  loading: boolean;
}

export interface DCFAssumption {
  label: string;
  value: string | number;
  sensitivity?: boolean;
}

export interface FairValueData {
  fairValue: number;
  currentPrice: number;
  currency: string;
  upside: number;
  confidence: "high" | "medium" | "low";
}

export interface SensitivityCell {
  row: string;
  col: string;
  value: number;
  isBase?: boolean;
}

export interface YearProjection {
  year: string;
  revenue: number;
  growth: number;
  ebitda: number;
  margin: number;
  fcf: number;
}

export interface ModelPanelState {
  fairValue: FairValueData | null;
  assumptions: DCFAssumption[];
  impliedMultiples: { label: string; value: string | number }[];
  sensitivityData: SensitivityCell[];
  sensitivityRowLabel: string;
  sensitivityColLabel: string;
  sensitivityRowValues: string[];
  sensitivityColValues: string[];
  yearByYear: YearProjection[];
  loading: boolean;
}

export interface PeerCompany {
  ticker: string;
  name: string;
  marketCap: number;
  peRatio: number;
  evEbitda: number;
  revenueGrowth: number;
  margin: number;
  [key: string]: string | number;
}

export interface ScatterPoint {
  ticker: string;
  x: number;
  y: number;
  isTarget?: boolean;
}

export interface CompsPanelState {
  peers: PeerCompany[];
  scatterData: ScatterPoint[];
  scatterXLabel: string;
  scatterYLabel: string;
  loading: boolean;
}

export interface MemoryPanelState {
  calibrationHits: number;
  calibrationMisses: number;
  recentRecalls: { company: string; date: string; relevance: number }[];
  loading: boolean;
}

/**
 * Matches backend GET /api/watchlist response shape.
 */
export interface WatchlistAlert {
  type: string;
  message: string;
}

export interface WatchlistItem {
  ticker: string;
  fair_value: number | null;
  market_price: number | null;
  gap: number | null;
  thesis: string | null;
  alerts: WatchlistAlert[];
}
