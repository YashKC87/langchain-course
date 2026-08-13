import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Cloud,
  Radio,
} from 'lucide-react';
import { api, formatApiError } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type {
  ActivityEvent,
  AgentMeteringRow,
  AttentionItem,
  Execution,
  MCPSummary,
  ModelSummary,
  OptimizationFinding,
  OverviewKPIs,
  RAGSummary,
  ToolSummary,
} from '../types';
import { ActivityFeed } from '../components/ActivityFeed';
import { AgentTable } from '../components/AgentTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { MetricCard } from '../components/MetricCard';
import { NeedsAttentionPanel } from '../components/NeedsAttentionPanel';
import { OptimizationPanel } from '../components/OptimizationPanel';
import { SectionTile } from '../components/SectionTile';
import { displayOrDash, formatDuration, formatNumber } from '../utils/format';

export function OverviewPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState<{ title: string; message: string; actions?: Array<{ label: string; action: string; id: string }> } | null>(null);
  const [kpis, setKpis] = useState<OverviewKPIs | null>(null);
  const [metering, setMetering] = useState<AgentMeteringRow[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [tools, setTools] = useState<ToolSummary[]>([]);
  const [mcp, setMcp] = useState<MCPSummary[]>([]);
  const [rag, setRag] = useState<RAGSummary[]>([]);
  const [optimization, setOptimization] = useState<OptimizationFinding[]>([]);
  const [liveExecutions, setLiveExecutions] = useState<Execution[]>([]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [
        overview,
        meteringRes,
        activityRes,
        attentionRes,
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
      setModels(!modelsRes.empty ? modelsRes.items : []);
      setTools(!toolsRes.empty ? toolsRes.items : []);
      setMcp(!mcpRes.empty ? mcpRes.items : []);
      setRag(!ragRes.empty ? ragRes.items : []);
      setOptimization(!optRes.empty ? optRes.items : []);
      setLiveExecutions(!execRes.empty ? execRes.items.slice(0, 6) : []);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30);

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
            <h2 className="panel-title">Live Executions</h2>
            <p className="panel-subtitle">Recent agent runs · open Live Executions for full workflow traces</p>
          </div>
          <button type="button" className="btn" onClick={() => navigate('/live-executions')}>
            Open live view
          </button>
        </div>
        {liveExecutions.length === 0 ? (
          <EmptyState
            title="No live executions"
            message="Run an agent or wait for Application Insights telemetry."
            compact
          />
        ) : (
          <div className="grid-kpi live-executions-kpi">
            {liveExecutions.map((e) => (
              <MetricCard
                key={e.execution_id}
                label={displayOrDash(e.agent_name)}
                displayValue={formatNumber(e.total_tokens)}
                subtitle={`${e.status} · ${formatDuration(e.execution_duration_ms)}`}
                onClick={() => navigate('/live-executions')}
              />
            ))}
          </div>
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

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Needs Attention</h2>
        </div>
        <NeedsAttentionPanel items={attention} />
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
