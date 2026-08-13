import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Boxes,
  BrainCircuit,
  Cable,
  Cloud,
  GitBranch,
  Network,
  Radio,
  Sparkles,
  Wrench,
} from 'lucide-react';
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
import { SectionTile } from '../components/SectionTile';
import { WorkflowGraph } from '../components/WorkflowGraph';
import { displayOrDash, formatNumber, formatRelative, statusTone } from '../utils/format';

function pickRunningExecution(items: Execution[]): Execution | null {
  const running = items.filter((e) => e.status === 'running');
  if (!running.length) return null;
  return [...running].sort((a, b) => {
    const at = a.start_time ?? a.timestamp ?? '';
    const bt = b.start_time ?? b.timestamp ?? '';
    return String(bt).localeCompare(String(at));
  })[0];
}

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
  const [runningExecution, setRunningExecution] = useState<Execution | null>(null);
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

      const liveItems = !execRes.empty ? execRes.items : [];
      const running = pickRunningExecution(liveItems);
      setRunningExecution(running);
      if (running) {
        try {
          setWorkflow(await api.getExecutionWorkflow(running.execution_id));
        } catch {
          setWorkflow(null);
        }
      } else {
        setWorkflow(null);
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

  const sectionTiles = [
    {
      title: 'Agents',
      description: 'Metering and health across discovered agents',
      icon: Boxes,
      value: formatNumber(metering.length || null),
      path: '/agents',
    },
    {
      title: 'Live Executions',
      description: 'Running and recent agent executions',
      icon: Radio,
      value: formatNumber(kpis?.executions?.value ?? null),
      path: '/live-executions',
      tone: runningExecution ? ('running' as const) : ('default' as const),
    },
    {
      title: 'Workflow',
      description: 'Graphical path for the active agent run',
      icon: GitBranch,
      value: runningExecution ? 'Live' : 'Idle',
      path: '/workflow',
      tone: runningExecution ? ('running' as const) : ('default' as const),
    },
    {
      title: 'Models',
      description: 'Token and latency by model',
      icon: BrainCircuit,
      value: formatNumber(models.length || null),
      path: '/models',
    },
    {
      title: 'Tools & MCP',
      description: 'Tool and MCP invocation telemetry',
      icon: Wrench,
      value: formatNumber((tools.length || 0) + (mcp.length || 0) || null),
      path: '/tools-mcp',
    },
    {
      title: 'RAG',
      description: 'Retrieval and knowledge-source activity',
      icon: Network,
      value: formatNumber(rag.length || null),
      path: '/rag',
    },
    {
      title: 'Multi-Agent / A2A',
      description: 'Agent-to-agent handoffs',
      icon: Cable,
      path: '/a2a',
    },
    {
      title: 'Integrations',
      description: 'Cloud and observability connections',
      icon: Cable,
      value: formatNumber(health.filter((h) => h.enabled).length || null),
      path: '/integrations',
    },
    {
      title: 'Observability',
      description: 'Traces, freshness, and signal quality',
      icon: Activity,
      path: '/observability',
    },
    {
      title: 'Optimization',
      description: 'Recommendations from live evidence',
      icon: Sparkles,
      value: formatNumber(optimization.length || null),
      path: '/optimization',
    },
  ];

  return (
    <div className="stack">
      <div className="grid-kpi">
        <MetricCard label="Active Agents" metric={kpis?.active_agents} onClick={() => navigate('/agents')} />
        <MetricCard label="Executions" metric={kpis?.executions} onClick={() => navigate('/live-executions')} />
        <MetricCard label="Total Tokens" metric={kpis?.total_tokens} onClick={() => navigate('/models')} />
        <MetricCard label="Success Rate" metric={kpis?.success_rate} format="percent" onClick={() => navigate('/agents')} />
        <MetricCard label="Avg Latency" metric={kpis?.average_latency} format="duration" onClick={() => navigate('/live-executions')} />
        <MetricCard label="Needs Attention" metric={kpis?.needs_attention} onClick={() => navigate('/optimization')} />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Sections</h2>
            <p className="panel-subtitle">Select a tile to open its information window</p>
          </div>
        </div>
        <div className="section-tile-grid">
          {sectionTiles.map((tile) => (
            <SectionTile
              key={tile.path}
              title={tile.title}
              description={tile.description}
              icon={tile.icon}
              value={tile.value}
              tone={tile.tone}
              onClick={() => navigate(tile.path)}
            />
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Live Agent Workflow</h2>
            <p className="panel-subtitle">
              {runningExecution
                ? `${runningExecution.agent_name ?? 'Agent'} · ${runningExecution.execution_id.slice(0, 12)}… · running`
                : 'Shows only the agent execution that is currently running'}
            </p>
          </div>
          {runningExecution ? (
            <button type="button" className="btn" onClick={() => navigate('/live-executions')}>
              Open live view
            </button>
          ) : null}
        </div>
        {runningExecution && workflow ? (
          <WorkflowGraph graph={workflow} highlightRunning height={440} />
        ) : (
          <EmptyState
            title="No agent currently running"
            message="The live workflow appears here only while an agent execution is in progress."
            compact
          />
        )}
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
            <button type="button" className="btn" onClick={() => navigate('/models')}>
              Open models
            </button>
          </div>
          {models.length === 0 ? (
            <EmptyState title="No model activity" message="Model metrics appear when live token telemetry arrives." compact />
          ) : (
            <div className="section-tile-grid">
              {models.slice(0, 6).map((m) => (
                <SectionTile
                  key={m.model}
                  title={m.model}
                  description={displayOrDash(m.provider)}
                  value={formatNumber(m.tokens)}
                  meta={`${formatNumber(m.requests)} requests`}
                  onClick={() => navigate('/models')}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Agent Metering</h2>
          <button type="button" className="btn" onClick={() => navigate('/agents')}>
            Open agents
          </button>
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
            <button type="button" className="btn" onClick={() => navigate('/integrations')}>
              Open integrations
            </button>
          </div>
          {health.length === 0 ? (
            <EmptyState title="Integration Required" message="Connect a platform to monitor integration health." compact />
          ) : (
            <div className="section-tile-grid compact">
              {health.map((h) => (
                <div key={h.id} className="section-tile interactive" style={{ cursor: 'default' }}>
                  <button
                    type="button"
                    onClick={() => navigate('/integrations')}
                    style={{
                      all: 'unset',
                      cursor: 'pointer',
                      display: 'block',
                      width: '100%',
                    }}
                  >
                    <div className="section-tile-title">{h.name}</div>
                    <div className="section-tile-meta" style={{ marginTop: 6 }}>
                      <span className={`badge ${statusTone(h.status)}`}>{h.status.replace(/_/g, ' ')}</span>
                      <span>last {formatRelative(h.last_telemetry_at)}</span>
                    </div>
                  </button>
                  <div
                    style={{ marginTop: 8 }}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <IntegrationSwitch
                      enabled={h.enabled}
                      disabled={toggling === h.id || (h.configured === false && !h.enabled)}
                      onChange={(on) => void toggleHealth(h, on)}
                    />
                  </div>
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
            <div className="section-tile-grid compact">
              {tools.slice(0, 6).map((t) => (
                <SectionTile
                  key={`${t.name}-${t.agent_id}`}
                  title={t.name}
                  value={formatNumber(t.calls)}
                  meta="calls"
                  onClick={() => navigate('/tools-mcp')}
                />
              ))}
            </div>
          )}
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">MCP</h2>
          </div>
          {mcp.length === 0 ? (
            <EmptyState title="No MCP telemetry" message="MCP server activity requires live MCP spans." compact />
          ) : (
            <div className="section-tile-grid compact">
              {mcp.slice(0, 6).map((m) => (
                <SectionTile
                  key={`${m.server}-${m.tool}`}
                  title={m.server}
                  description={m.tool ?? undefined}
                  value={formatNumber(m.calls)}
                  onClick={() => navigate('/tools-mcp')}
                />
              ))}
            </div>
          )}
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">RAG</h2>
          </div>
          {rag.length === 0 ? (
            <EmptyState title="No RAG telemetry" message="Retrieval metrics appear when RAG queries are traced." compact />
          ) : (
            <div className="section-tile-grid compact">
              {rag.slice(0, 6).map((r) => (
                <SectionTile
                  key={`${r.knowledge_source}-${r.agent_id}`}
                  title={r.knowledge_source}
                  value={formatNumber(r.queries)}
                  meta="queries"
                  onClick={() => navigate('/rag')}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Optimization</h2>
          <button type="button" className="btn" onClick={() => navigate('/optimization')}>
            Open optimization
          </button>
        </div>
        <OptimizationPanel items={optimization} />
      </div>
    </div>
  );
}
