/**
 * Shared TypeScript Contracts & Schemas for Runwise
 * Aligned 1-to-1 with backend Pydantic models in src/runwise/service/schemas.py
 */

export type GraderStatus = "PASS" | "FAIL" | "NOT_APPLICABLE" | "NOT_EVALUATED";

export interface GraderDetail {
  status: GraderStatus;
  reason_code?: string | null;
  message?: string | null;
}

export interface EvaluationSummary {
  overall_status: GraderStatus;
  task_completion: GraderDetail;
  policy_compliance: GraderDetail;
  groundedness: GraderDetail;
  explanation: string;
}

export interface SanitizedToolCall {
  id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: "success" | "error";
  result_data?: Record<string, unknown> | null;
  error_message?: string | null;
}

export type TimelineEventType =
  | "REQUEST_RECEIVED"
  | "ROUTING_DECISION"
  | "MODEL_INVOCATION"
  | "TOOL_EXECUTION"
  | "FINAL_RESPONSE"
  | "EVALUATION";

export interface SanitizedTimelineEvent {
  seq: number;
  event_type: TimelineEventType;
  timestamp_iso: string;
  summary: string;
  details?: Record<string, unknown>;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface AgentRunResponse {
  session_id: string;
  response: string;
  exit_reason: string;
  step_count: number;
  tokens: TokenUsage;
  latency_ms: float_number;
  model: string;
  prompt_version: string;
  variant: string;
  complexity_score?: number | null;
  routing_reason?: string | null;
  features_detected?: string[];
  cost_usd?: number | null;
  is_replay?: boolean;
  tool_calls: SanitizedToolCall[];
  events: SanitizedTimelineEvent[];
  evaluation?: EvaluationSummary | null;
}

export type float_number = number;

export interface AgentRunRequest {
  prompt: string;
  session_id?: string;
  customer_id?: string | null;
  task_id?: string;
  auto_route?: boolean;
  mode?: "scenario" | "conversation";
}

export interface ScenarioDefinition {
  id: string;
  title: string;
  category: "inquiry" | "mutation" | "refund" | "dispute" | "adversarial";
  expected_tier: "flash" | "pro";
  task_id: string;
  customer_id?: string | null;
  badge: string;
  description: string;
  prompt: string;
  expected_route_reason: string;
  expected_tools: string[];
}

export interface RoutingBenchmarkItem {
  strategy: string;
  methodology: "Live Vertex AI" | "Empirical Trace Replay";
  accuracy: string;
  costPer1k: string;
  vsProCostDelta: string;
  p50Latency: string;
  p95Latency: string;
  trafficSplit: string;
  isRecommended?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  runData?: AgentRunResponse;
  metadata?: {
    model?: string;
    tokens?: TokenUsage;
    latency_ms?: number;
    cost_usd?: number;
    is_replay?: boolean;
    complexity_score?: number | null;
    eval_verdict?: GraderStatus;
  };
}
