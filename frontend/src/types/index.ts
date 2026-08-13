/** Domain types aligned with backend — no financial fields. */

export type IntegrationStatus =
  | 'connected'
  | 'telemetry_active'
  | 'warning'
  | 'connection_failed'
  | 'disabled'
  | 'not_configured';

export type AgentHealth =
  | 'healthy'
  | 'warning'
  | 'critical'
  | 'offline'
  | 'unknown'
  | 'paused';

export type ExecutionStatus =
  | 'running'
  | 'success'
  | 'failed'
  | 'timeout'
  | 'cancelled'
  | 'unknown';

export type TelemetryQuality =
  | 'complete'
  | 'partial'
  | 'delayed'
  | 'missing'
  | 'provider_unsupported'
  | 'not_used'
  | 'not_provided';

export type WorkflowNodeType =
  | 'user'
  | 'agent'
  | 'router'
  | 'planner'
  | 'worker'
  | 'model'
  | 'tool'
  | 'mcp'
  | 'rag'
  | 'database'
  | 'api'
  | 'a2a'
  | 'guardrail'
  | 'response'
  | 'unknown';

export type AttentionSeverity = 'info' | 'warning' | 'critical';

export interface MetricValue {
  value: number | null;
  available: boolean;
  label?: string | null;
  unit?: string | null;
}

export interface EmptyStateResponse {
  empty: true;
  title: string;
  message: string;
  actions?: Array<{ label: string; action: string; id: string }>;
  items?: never[];
}

export interface OverviewKPIs {
  active_agents: MetricValue;
  executions: MetricValue;
  total_tokens: MetricValue;
  success_rate: MetricValue;
  average_latency: MetricValue;
  needs_attention: MetricValue;
  telemetry_live: boolean;
  last_updated: string | null;
}

export type OverviewResponse =
  | EmptyStateResponse
  | { empty: false; kpis: OverviewKPIs };

export interface StatusResponse {
  app: string;
  telemetry_live: boolean;
  last_updated: string | null;
  enabled_integrations: number;
  agents: number;
  executions: number;
}

export interface IntegrationConfig {
  fields: Record<string, unknown>;
  secret_refs: Record<string, string>;
  auth_method?: string | null;
}

export interface EnableProgressStage {
  name: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped';
  message?: string | null;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  provider: string;
  status: IntegrationStatus;
  enabled: boolean;
  configured: boolean;
  config: IntegrationConfig;
  last_telemetry_at: string | null;
  agents_discovered: number | null;
  connection_health: string | null;
  auth_state: string | null;
  error_message: string | null;
  enable_progress: EnableProgressStage[];
}

export interface Agent {
  id: string;
  name: string;
  description?: string | null;
  version?: string | null;
  cloud?: string | null;
  platform?: string | null;
  framework?: string | null;
  environment?: string | null;
  region?: string | null;
  owner?: string | null;
  business_unit?: string | null;
  application?: string | null;
  primary_model?: string | null;
  fallback_model?: string | null;
  endpoint_ref?: string | null;
  telemetry_source?: string | null;
  integration_id?: string | null;
  status?: string | null;
  health: AgentHealth;
  first_seen_at?: string | null;
  last_execution_at?: string | null;
  last_telemetry_at?: string | null;
}

export interface AgentMeteringRow {
  agent_id: string;
  agent_name: string;
  cloud?: string | null;
  platform?: string | null;
  framework?: string | null;
  model?: string | null;
  executions?: number | null;
  tokens?: number | null;
  average_steps?: number | null;
  model_calls?: number | null;
  tool_calls?: number | null;
  mcp_calls?: number | null;
  rag_calls?: number | null;
  a2a_calls?: number | null;
  average_latency_ms?: number | null;
  success_rate?: number | null;
  health: AgentHealth;
  last_seen?: string | null;
}

export interface Execution {
  execution_id: string;
  timestamp?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  cloud_provider?: string | null;
  platform?: string | null;
  framework?: string | null;
  environment?: string | null;
  model_name?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  model_calls?: number | null;
  agent_steps?: number | null;
  tool_calls?: number | null;
  mcp_calls?: number | null;
  rag_queries?: number | null;
  a2a_calls?: number | null;
  retry_count?: number | null;
  fallback_count?: number | null;
  execution_duration_ms?: number | null;
  status: ExecutionStatus;
  error_count?: number | null;
  error_type?: string | null;
  telemetry_quality?: TelemetryQuality;
  trace_id?: string | null;
}

export interface WorkflowNode {
  id: string;
  name: string;
  node_type: WorkflowNodeType;
  status?: string | null;
  duration_ms?: number | null;
  tokens?: number | null;
  call_count?: number | null;
  timestamp?: string | null;
  is_live?: boolean;
  span_id?: string | null;
  attributes?: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  edge_type?: string;
  label?: string | null;
}

export interface WorkflowGraph {
  execution_id: string;
  trace_id?: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  status: ExecutionStatus;
}

export interface WaterfallItem {
  span_id: string;
  name: string;
  node_type?: string;
  status?: string | null;
  start_offset_ms: number;
  duration_ms: number;
  depth?: number;
  tokens?: number | null;
}

export interface ActivityEvent {
  id: string;
  timestamp: string;
  event_type: string;
  message: string;
  agent_id?: string | null;
  agent_name?: string | null;
  severity: string;
  execution_id?: string | null;
  trace_id?: string | null;
}

export interface AttentionItem {
  id: string;
  condition: string;
  severity: AttentionSeverity;
  message: string;
  agent_id?: string | null;
  agent_name?: string | null;
  component?: string | null;
  evidence?: string | null;
  related_trace?: string | null;
  detected_at: string;
}

export interface OptimizationFinding {
  id: string;
  observation: string;
  evidence: string;
  affected_agent?: string | null;
  affected_component?: string | null;
  recommendation: string;
  confidence: number;
  severity: AttentionSeverity;
  related_trace?: string | null;
  detected_at: string;
}

export interface ModelSummary {
  model: string;
  provider?: string | null;
  cloud?: string | null;
  agents_using?: number | null;
  requests?: number | null;
  tokens?: number | null;
  average_latency_ms?: number | null;
  success_rate?: number | null;
  failure_rate?: number | null;
  fallback_count?: number | null;
  last_seen?: string | null;
}

export interface ToolSummary {
  name: string;
  tool_type?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  calls?: number | null;
  success?: number | null;
  failure?: number | null;
  average_latency_ms?: number | null;
  retries?: number | null;
  last_invocation?: string | null;
  health?: string | null;
}

export interface MCPSummary {
  server: string;
  tool?: string | null;
  connected_agents?: number | null;
  calls?: number | null;
  success?: number | null;
  failure?: number | null;
  timeouts?: number | null;
  auth_errors?: number | null;
  average_latency_ms?: number | null;
  retries?: number | null;
  last_invocation?: string | null;
  health?: string | null;
}

export interface RAGSummary {
  knowledge_source: string;
  agent_id?: string | null;
  agent_name?: string | null;
  queries?: number | null;
  search_type?: string | null;
  documents_retrieved?: number | null;
  chunks_retrieved?: number | null;
  average_latency_ms?: number | null;
  empty_retrievals?: number | null;
  failures?: number | null;
  retries?: number | null;
  last_query?: string | null;
}

export interface A2ASummary {
  source_agent: string;
  destination_agent: string;
  protocol?: string | null;
  handoffs?: number | null;
  success?: number | null;
  failure?: number | null;
  average_latency_ms?: number | null;
  tokens?: number | null;
  retries?: number | null;
  last_activity?: string | null;
}

export interface TraceSummary {
  trace_id: string;
  span_count: number;
  root_name?: string | null;
  start_time?: string | null;
}

export interface AppSettings {
  telemetry_retention_days: number;
  auto_refresh_seconds: number;
  runaway_steps_warning: number;
  runaway_steps_high: number;
  runaway_steps_critical: number;
  runaway_retry_threshold: number;
  runaway_fallback_threshold: number;
  runaway_duration_ms_threshold: number;
  latency_warning_ms: number;
  latency_critical_ms: number;
  content_capture_enabled: boolean;
  pii_redaction_enabled: boolean;
  telemetry_sampling_rate: number;
  efficiency_weights: Record<string, number>;
  agent_discovery_schedule_minutes: number;
}

export interface GlobalFilters {
  cloud: string;
  platform: string;
  tenant: string;
  business_unit: string;
  environment: string;
  agent: string;
  framework: string;
  model: string;
  status: string;
  time_range: string;
}

export interface ListResponse<T> {
  empty: boolean;
  title?: string;
  message?: string;
  actions?: Array<{ label: string; action: string; id: string }>;
  items: T[];
}

export interface IntegrationHealthItem {
  id: string;
  name: string;
  status: IntegrationStatus;
  enabled: boolean;
  configured: boolean;
  last_telemetry_at?: string | null;
  agents_discovered?: number | null;
  error_message?: string | null;
  connection_health?: string | null;
}
