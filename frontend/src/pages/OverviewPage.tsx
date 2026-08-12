import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cloud, Radio } from 'lucide-react';
import { api, formatApiError } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type {
  ActivityEvent,
  AgentMeteringRow,
  AttentionItem,
  Execution,
  IntegrationHealthItem,
  MCPSummary,
  ModelSummary,
  OptimizationFinding,
  OverviewKPIs,
  RAGSummary,
  ToolSummary,
  WorkflowGraph as WFGraph,
} from '../types';
import { ActivityFeed } from '../components/ActivityFeed';
import { AgentTable } from '../components/AgentTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { IntegrationSwitch } from '../components/IntegrationSwitch';
import { LoadingState } from '../components/LoadingState';
import { MetricCard } from '../components/MetricCard';
import { NeedsAttentionPanel } from '../components/NeedsAttentionPanel';
import { OptimizationPanel } from '../components/OptimizationPanel';
import { WorkflowGraph } from '../components/WorkflowGraph';
import { displayOrDash, formatNumber, formatRelative, statusTone } from '../utils/format';

export function OverviewPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState<{ title: string; message: string; actions?: Array<{ label: string; action: string; id: string }> } | null>(null);
  const [kpis, setKpis] = useState<OverviewKPIs | null>(null);
  const [metering, setMetering] = useState<AgentMeteringRow[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [health, setHealth] = useState<IntegrationHealthItem[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [tools, setTools] = useState<ToolSummary[]>([]);
  const [mcp, setMcp] = useState<MCPSummary[]>([]);
  const [rag, setRag] = useState<RAGSummary[]>([]);
  const [optimization, setOptimization] = useState<OptimizationFinding[]>([]);
  const [workflow, setWorkflow] = useState<WFGraph | null>(null);
  const [liveExecution, setLiveExecution] = useState<Execution | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [
        overview,
        meteringRes,
        activityRes,
        attentionRes,
        healthRes,
        modelsRes,
        toolsRes,
        mcpRes,
        ragRes,
        optRes,
        execRes,
      ] = await Promise.all([
        api.getOverview(),
        api.getAgentMetering(),
        api.getActivity(),
        api.getNeedsAttention(),
        api.getIntegrationHealth(),
        api.getModels(),
        api.getTools(),
        api.getMcp(),
        api.getRag(),
        api.getOptimization(),
        api.getExecutions({ live_only: true }),
      ]);

      if (overview.empty) {
        setEmpty({ title: overview.title, message: overview.message, actions: overview.actions });
        setKpis(null);
      } else {
        setEmpty(null);
        setKpis(overview.kpis);
      }

      setMetering(!meteringRes.empty ? meteringRes.items : []);
      setActivity(!activityRes.empty ? activityRes.items : []);
      setAttention(!attentionRes.empty ? attentionRes.items : []);
      setHealth(healthRes.items ?? []);
      setModels(!modelsRes.empty ? modelsRes.items : []);
      setTools(!toolsRes.empty ? toolsRes.items : []);
      setMcp(!mcpRes.empty ? mcpRes.items : []);
      setRag(!ragRes.empty ? ragRes.items : []);
      setOptimization(!optRes.empty ? optRes.items : []);

      const live = !execRes.empty && execRes.items.length ? execRes.items[0] : null;
      setLiveExecution(live);
      if (live) {
        try {
          setWorkflow(await api.getExecutionWorkflow(live.execution_id));
        } catch {
          setWorkflow(null);
        }
      } else {
        // Fall back to most recent execution for workflow centerpiece
        const all = await api.getExecutions();
        if (!all.empty && all.items.length) {
          const first = all.items[0];
          setLiveExecution(first);
          try {
            setWorkflow(await api.getExecutionWorkflow(first.execution_id));
          } catch {
            setWorkflow(null);
          }
        } else {
          setWorkflow(null);
        }
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30);

  const toggleHealth = async (item: IntegrationHealthItem, enabled: boolean) => {
    setToggling(item.id);
    try {
      await api.toggleIntegration(item.id, enabled);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Toggle failed');
    } finally {
      setToggling(null);
    }
  };

  if (loading) return <LoadingState label="Loading overview…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  if (empty) {
    return (
      <div className="panel connect-first-panel">
        <EmptyState
          title={empty.title}
          message={empty.message}
          icon={<Cloud size={36} strokeWidth={1.4} style={{ opacity: 0.55 }} />}
          actions={
            empty.actions?.length ? (
              <div className="connect-grid">
                {empty.actions
                  .slice()
                  .sort((a, b) => (a.id === 'azure' ? -1 : b.id === 'azure' ? 1 : 0))
                  .map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    className={`connect-card${a.id === 'azure' ? ' connect-card-recommended' : ''}`}
                    onClick={() => navigate('/integrations', { state: { focus: a.id } })}
                  >
                    <Radio size={22} />
                    <div className="connect-card-title">{a.label}</div>
                    {a.id === 'azure' ? (
                      <div className="connect-card-badge">Recommended start</div>
                    ) : null}
                    <div className="muted" style={{ fontSize: 12 }}>
                      Connect
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => navigate('/integrations')}>
                Open Integrations
              </button>
            )
          }
        />
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="grid-kpi">
        <MetricCard label="Active Agents" metric={kpis?.active_agents} />
        <MetricCard label="Executions" metric={kpis?.executions} />
        <MetricCard label="Total Tokens" metric={kpis?.total_tokens} />
        <MetricCard label="Success Rate" metric={kpis?.success_rate} format="percent" />
        <MetricCard label="Avg Latency" metric={kpis?.average_latency} format="duration" />
        <MetricCard label="Needs Attention" metric={kpis?.needs_attention} />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Live Agent Workflow</h2>
            <p className="panel-subtitle">
              {liveExecution
                ? `${liveExecution.agent_name ?? 'Agent'} · ${liveExecution.execution_id.slice(0, 12)}… · ${liveExecution.status}`
                : 'Graphical execution path from live telemetry'}
            </p>
          </div>
        </div>
        <WorkflowGraph graph={workflow} height={440} />
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Agent Activity</h2>
          </div>
          <ActivityFeed items={activity} />
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Model / Token Activity</h2>
          </div>
          {models.length === 0 ? (
            <EmptyState title="No model activity" message="Model metrics appear when live token telemetry arrives." compact />
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Provider</th>
                    <th>Requests</th>
                    <th>Tokens</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {models.slice(0, 8).map((m) => (
                    <tr key={m.model}>
                      <td className="mono">{m.model}</td>
                      <td>{displayOrDash(m.provider)}</td>
                      <td className="mono">{formatNumber(m.requests)}</td>
                      <td className="mono">{formatNumber(m.tokens)}</td>
                      <td className="mono">{m.average_latency_ms == null ? '—' : `${Math.round(m.average_latency_ms)}ms`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Agent Metering</h2>
        </div>
        <AgentTable rows={metering} />
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Needs Attention</h2>
          </div>
          <NeedsAttentionPanel items={attention} />
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Integration Health</h2>
          </div>
          {health.length === 0 ? (
            <EmptyState title="Integration Required" message="Connect a platform to monitor integration health." compact />
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {health.map((h) => (
                <div
                  key={h.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '8px 0',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 550 }}>{h.name}</div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      <span className={`badge ${statusTone(h.status)}`}>{h.status.replace(/_/g, ' ')}</span>
                      {' · '}
                      last {formatRelative(h.last_telemetry_at)}
                      {!h.enabled && h.configured ? ' · Historical telemetry retained' : ''}
                    </div>
                  </div>
                  <IntegrationSwitch
                    enabled={h.enabled}
                    disabled={toggling === h.id || (h.configured === false && !h.enabled)}
                    onChange={(on) => void toggleHealth(h, on)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid-3">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Tools</h2>
          </div>
          {tools.length === 0 ? (
            <EmptyState title="No tool telemetry" message="Tool calls appear when spans include tool invocations." compact />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16, color: 'var(--text-secondary)' }}>
              {tools.slice(0, 6).map((t) => (
                <li key={`${t.name}-${t.agent_id}`}>
                  {t.name} · {formatNumber(t.calls)} calls
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">MCP</h2>
          </div>
          {mcp.length === 0 ? (
            <EmptyState title="No MCP telemetry" message="MCP server activity requires live MCP spans." compact />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16, color: 'var(--text-secondary)' }}>
              {mcp.slice(0, 6).map((m) => (
                <li key={`${m.server}-${m.tool}`}>
                  {m.server}
                  {m.tool ? ` / ${m.tool}` : ''} · {formatNumber(m.calls)}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">RAG</h2>
          </div>
          {rag.length === 0 ? (
            <EmptyState title="No RAG telemetry" message="Retrieval metrics appear when RAG queries are traced." compact />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16, color: 'var(--text-secondary)' }}>
              {rag.slice(0, 6).map((r) => (
                <li key={`${r.knowledge_source}-${r.agent_id}`}>
                  {r.knowledge_source} · {formatNumber(r.queries)} queries
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Optimization</h2>
        </div>
        <OptimizationPanel items={optimization} />
      </div>
    </div>
  );
}
