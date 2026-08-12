import type {
  A2ASummary,
  Agent,
  AgentMeteringRow,
  AppSettings,
  AttentionItem,
  EmptyStateResponse,
  Execution,
  Integration,
  IntegrationHealthItem,
  ListResponse,
  MCPSummary,
  ModelSummary,
  OptimizationFinding,
  OverviewResponse,
  RAGSummary,
  StatusResponse,
  ToolSummary,
  TraceSummary,
  WaterfallItem,
  WorkflowGraph,
} from '../types';

/** Same-origin `/api/v1` uses the Vite dev proxy or nginx in production. */
function resolveApiBase(): string {
  const envUrl = import.meta.env.VITE_API_URL?.trim();
  if (envUrl) return envUrl.replace(/\/$/, '');

  // Dev + docker/nginx: proxy /api → backend (only expose one port)
  if (import.meta.env.DEV || import.meta.env.PROD) {
    return '/api/v1';
  }

  return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
}

export const API_BASE = resolveApiBase();

export class ApiError extends Error {
  status: number;
  body: unknown;
  isNetworkError: boolean;

  constructor(status: number, message: string, body?: unknown, isNetworkError = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    this.isNetworkError = isNetworkError;
  }
}

export function formatApiError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.isNetworkError) {
      return (
        'Cannot reach the Control Center API. The backend must be running before the UI can load data.\n\n' +
        'Start it with:\n' +
        '  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000\n\n' +
        'Or run both services:\n' +
        '  ./scripts/dev.sh\n\n' +
        'Then open the UI at http://localhost:5173 (not a static file URL).'
      );
    }
    return err.message;
  }
  if (err instanceof TypeError && /fetch|network/i.test(err.message)) {
    return formatApiError(new ApiError(0, 'Failed to fetch', null, true));
  }
  return err instanceof Error ? err.message : 'Request failed';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, 'Failed to fetch', null, true);
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    const detail =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail || `Request failed (${res.status})`, body);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function qs(params?: Record<string, string | boolean | number | undefined | null>): string {
  if (!params) return '';
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const api = {
  getStatus: () => request<StatusResponse>('/status'),

  getOverview: () => request<OverviewResponse>('/overview'),

  getIntegrationHealth: () =>
    request<{ items: IntegrationHealthItem[] }>('/overview/integration-health'),

  getNeedsAttention: () =>
    request<ListResponse<AttentionItem> | EmptyStateResponse>('/overview/needs-attention'),

  getActivity: (agent?: string) =>
    request<ListResponse<import('../types').ActivityEvent> | EmptyStateResponse>(
      `/overview/activity${qs({ agent })}`,
    ),

  getIntegrations: () =>
    request<{ groups: Record<string, Integration[]> }>('/integrations'),

  getIntegration: (id: string) => request<Integration>(`/integrations/${id}`),

  saveIntegrationConfig: (
    id: string,
    body: {
      fields: Record<string, unknown>;
      auth_method?: string | null;
      secret_refs?: Record<string, string>;
    },
  ) =>
    request<Integration>(`/integrations/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  testIntegration: (id: string) =>
    request<{ ok: boolean; stage: string; message: string }>(`/integrations/${id}/test`, {
      method: 'POST',
    }),

  toggleIntegration: (id: string, enabled: boolean) =>
    request<Integration>(`/integrations/${id}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  discoverIntegration: (id: string) =>
    request<{
      ok: boolean;
      message?: string;
      stage?: string;
      agents?: Array<Record<string, unknown>>;
      counts?: { created: number; updated: number; total: number };
      accounts_scanned?: string[];
      errors?: string[];
      subscription_id?: string;
      resource_group?: string;
      foundry_project?: string;
    }>(`/integrations/${id}/discover`, { method: 'POST' }),

  getAgents: () => request<ListResponse<Agent> | EmptyStateResponse>('/agents'),

  getAgentMetering: () =>
    request<ListResponse<AgentMeteringRow> | EmptyStateResponse>('/agents/metering'),

  getAgent: (id: string) =>
    request<{
      agent: Agent;
      execution_count: number | null;
      efficiency: Record<string, unknown> | null;
    }>(`/agents/${id}`),

  getAgentTelemetryQuality: (id: string) =>
    request<{ agent: string; dimensions: Record<string, string> }>(
      `/agents/${id}/telemetry-quality`,
    ),

  getExecutions: (params?: { live_only?: boolean; status?: string; agent?: string }) =>
    request<ListResponse<Execution> | EmptyStateResponse>(`/executions${qs(params)}`),

  getExecution: (id: string) => request<Execution>(`/executions/${id}`),

  getExecutionWorkflow: (id: string) => request<WorkflowGraph>(`/executions/${id}/workflow`),

  getExecutionWaterfall: (id: string) =>
    request<ListResponse<WaterfallItem> | EmptyStateResponse>(`/executions/${id}/waterfall`),

  getTraces: (params?: { agent?: string; trace_id?: string; execution_id?: string }) =>
    request<ListResponse<TraceSummary> | EmptyStateResponse>(`/traces${qs(params)}`),

  getTrace: (id: string) =>
    request<{ trace_id: string; spans: Array<Record<string, unknown>> }>(`/traces/${id}`),

  getModels: () => request<ListResponse<ModelSummary> | EmptyStateResponse>('/models'),

  getTools: () => request<ListResponse<ToolSummary> | EmptyStateResponse>('/tools'),

  getMcp: () => request<ListResponse<MCPSummary> | EmptyStateResponse>('/mcp'),

  getRag: () => request<ListResponse<RAGSummary> | EmptyStateResponse>('/rag'),

  getA2A: () => request<ListResponse<A2ASummary> | EmptyStateResponse>('/a2a'),

  getCloudAnalytics: () =>
    request<{ empty: boolean; title?: string; message?: string; distribution?: Record<string, number> }>(
      '/analytics/cloud',
    ),

  getFrameworkAnalytics: () =>
    request<{ empty: boolean; title?: string; message?: string; distribution?: Record<string, number> }>(
      '/analytics/frameworks',
    ),

  getCrossCloudAnalytics: () =>
    request<{ empty: boolean; title?: string; message?: string; items?: unknown[] }>(
      '/analytics/cross-cloud',
    ),

  getOptimization: () =>
    request<ListResponse<OptimizationFinding> | EmptyStateResponse>('/optimization'),

  getSettings: () => request<AppSettings>('/settings'),

  updateSettings: (body: AppSettings) =>
    request<AppSettings>('/settings', { method: 'PUT', body: JSON.stringify(body) }),
};
