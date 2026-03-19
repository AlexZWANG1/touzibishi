export type SSEEventType =
  | "tool_start"
  | "tool_end"
  | "text_delta"
  | "text"
  | "context_compacted"
  | "retry"
  | "error"
  | "system"
  | "steering"
  | "user_input_needed"
  | "analysis_complete"
  | "done";

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface ToolStartEvent {
  tool: string;
  args: Record<string, unknown>;
}

export interface ToolEndEvent {
  tool: string;
  status: string;
  result?: unknown;
}

export interface InputRequestEvent {
  question: string;
  context: string;
  options: string[];
}

export interface AnalysisStartRequest {
  query: string;
  contextDocs?: string[];
  mode?: 'analysis' | 'learning';
}

export interface AnalysisStartResponse {
  analysisId: string;
  streamUrl: string;
}

export interface SteeringRequest {
  message: string;
}

export interface InputResponseRequest {
  response: string;
}

export interface ApiError {
  detail: string;
  status: number;
}
