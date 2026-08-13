import { api } from '../api/client';
import type {
  AgentMeteringRow,
  AttentionItem,
  Execution,
  ModelSummary,
  OptimizationFinding,
  OverviewKPIs,
  StatusResponse,
} from '../types';

export interface ReportSnapshot {
  generatedAt: string;
  status: StatusResponse;
  kpis: OverviewKPIs | null;
  emptyMessage?: string;
  metering: AgentMeteringRow[];
  executions: Execution[];
  models: ModelSummary[];
  attention: AttentionItem[];
  optimization: OptimizationFinding[];
}

export async function loadReportSnapshot(): Promise<ReportSnapshot> {
  const [status, overview, meteringRes, execRes, modelsRes, attentionRes, optRes] =
    await Promise.all([
      api.getStatus(),
      api.getOverview(),
      api.getAgentMetering(),
      api.getExecutions({ live_only: true }),
      api.getModels(),
      api.getNeedsAttention(),
      api.getOptimization(),
    ]);

  return {
    generatedAt: new Date().toISOString(),
    status,
    kpis: overview.empty ? null : overview.kpis,
    emptyMessage: overview.empty ? overview.message : undefined,
    metering: !meteringRes.empty ? meteringRes.items : [],
    executions: !execRes.empty ? execRes.items : [],
    models: !modelsRes.empty ? modelsRes.items : [],
    attention: !attentionRes.empty ? attentionRes.items : [],
    optimization: !optRes.empty ? optRes.items : [],
  };
}

export function formatReportValue(value: number | null | undefined, suffix = ''): string {
  if (value == null || Number.isNaN(value)) return '—';
  const rounded = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return `${rounded}${suffix}`;
}
