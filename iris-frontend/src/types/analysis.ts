export type PageState = "IDLE" | "RUNNING" | "WAITING" | "COMPLETE";

export type Phase = "gather" | "analyze" | "evaluate" | "finalize";

export type ActiveTab = "report" | "fundamentals" | "data" | "model" | "comps" | "strategy";

export type EventColor = "green" | "blue" | "amber" | "gray" | "purple" | "gold";

export interface TimelineEvent {
  id: string;
  timestamp: number;
  tool: string;
  message: string;
  phase: Phase;
  color: EventColor;
  duration?: number;
  status: "running" | "complete" | "error";
  fullText?: string;
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
  isTarget?: boolean;
  [key: string]: string | number | boolean | undefined;
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

export interface StrategySignal {
  ticker: string;
  action: string;
  price: number;
  targetPrice: number;
  stopLoss: number;
  positionPct: number;
  catalysts: string;
  reasoning: string;
  suggestedShares: number;
  alreadyHeld: boolean;
}

export interface StrategyPosition {
  ticker: string;
  shares: number;
  avgCost: number;
  livePrice?: number | null;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  entryDate?: string | null;
}

export interface StrategyPortfolio {
  cash: number;
  totalMarketValue: number;
  totalPortfolioValue: number;
  totalUnrealizedPnl: number;
  totalRealizedPnl: number;
  totalReturnPct: number;
  positionCount: number;
  winLoss: string;
  investedPct: number;
  positions: StrategyPosition[];
}

export interface StrategyPanelState {
  signal: StrategySignal | null;
  portfolio: StrategyPortfolio | null;
  loading: boolean;
}

export interface ResearchSection {
  title: string;
  content: string;
  timestamp: number;
}

export interface FundamentalsPanelState {
  sections: ResearchSection[];
  loading: boolean;
}

export interface MemoryPanelState {
  calibrationHits: number;
  calibrationMisses: number;
  recentRecalls: { company: string; date: string; relevance: number }[];
  loading: boolean;
}

export interface WatchlistAlert {
  type: string;
  message: string;
}

export interface WatchlistItem {
  ticker: string;
  name: string | null;
  fair_value: number | null;
  market_price: number | null;
  gap: number | null;
  thesis: string | null;
  recommendation: string | null;
  latest_run_id: string | null;
  alerts: WatchlistAlert[];
}

export interface AnalysisSnapshot {
  id: string;
  query: string;
  ticker: string | null;
  status: string;
  created_at: string;
  reasoning_text: string;
  thinking_text: string;
  timeline: TimelineEvent[];
  panels: {
    data: DataPanelState;
    model: ModelPanelState;
    comps: CompsPanelState;
    strategy?: StrategyPanelState;
    memory: MemoryPanelState;
    fundamentals?: FundamentalsPanelState;
  };
  tokens_in: number;
  tokens_out: number;
  resumable?: boolean;
  turn_count?: number;
}

export interface HistoryItem {
  id: string;
  query: string;
  ticker: string | null;
  status: string;
  created_at: string;
  recommendation: string | null;
  tokens_in: number;
  tokens_out: number;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
}
