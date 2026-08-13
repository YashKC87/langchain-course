import { useCallback, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type {
  Agent,
  Execution,
  OptimizationFinding,
  TraceSummary,
  WaterfallItem,
  WorkflowGraph as WFGraph,
} from '../types';
import { AgentHealthBadge } from '../components/AgentHealthBadge';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { ExecutionWaterfall } from '../components/ExecutionWaterfall';
import { LoadingState } from '../components/LoadingState';
import { MetricCard } from '../components/MetricCard';
import { OptimizationPanel } from '../components/OptimizationPanel';
import { TelemetryQualityBadge } from '../components/TelemetryQualityBadge';
import { TraceExplorer } from '../components/TraceExplorer';
import { WorkflowGraph } from '../components/WorkflowGraph';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatRelative,
  formatTimestamp,
} from '../utils/format';

const TABS = [
  'Overview',
  'Live Executions',
  'Workflow',
  'Executions',
  'Tokens',
  'Models',
  'Steps',
  'Tools',
  'MCP',
  'RAG',
  'A2A',
  'Tracing',
  'Performance',
  'Errors',
  'Integrations',
  'Optimization',
] as const;

type Tab = (typeof TABS)[number];

export function AgentDetailPage() {
  const { agentId = '' } = useParams();
  const [tab, setTab] = useState<Tab>('Overview');
  const [agent, setAgent] = useState<Agent | null>(null);
  const [executionCount, setExecutionCount] = useState<number | null>(null);
  const [efficiency, setEfficiency] = useState<Record<string, unknown> | null>(null);
  const [quality, setQuality] = useState<Record<string, string> | null>(null);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [live, setLive] = useState<Execution[]>([]);
  const [workflow, setWorkflow] = useState<WFGraph | null>(null);
  const [waterfall, setWaterfall] = useState<WaterfallItem[]>([]);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [optimization, setOptimization] = useState<OptimizationFinding[]>([]);
  const [selectedExec, setSelectedExec] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!agentId) return;
    setError(null);
    try {
      const [detail, tq, execs, liveExecs, opt, tr] = await Promise.all([
        api.getAgent(agentId),
        api.getAgentTelemetryQuality(agentId),
        api.getExecutions({ agent: agentId }),
        api.getExecutions({ agent: agentId, live_only: true }),
        api.getOptimization(),
        api.getTraces({ agent: agentId }),
      ]);
      setAgent(detail.agent);
      setExecutionCount(detail.execution_count);
      setEfficiency(detail.efficiency);
      setQuality(tq.dimensions);
      setExecutions(!execs.empty ? execs.items : []);
      setLive(!liveExecs.empty ? liveExecs.items : []);
      setOptimization(
        !opt.empty ? opt.items.filter((o) => o.affected_agent === agentId || o.affected_agent === detail.agent.name) : [],
      );
      setTraces(!tr.empty ? tr.items : []);

      const pick =
        (!liveExecs.empty && liveExecs.items[0]?.execution_id) ||
        (!execs.empty && execs.items[0]?.execution_id) ||
        null;
      const execId = selectedExec && (!execs.empty ? execs.items.some((e) => e.execution_id === selectedExec) : false)
        ? selectedExec
        : pick;
      setSelectedExec(execId);
      if (execId) {
        const [wf, wfFall] = await Promise.all([
          api.getExecutionWorkflow(execId),
          api.getExecutionWaterfall(execId),
        ]);
        setWorkflow(wf);
        setWaterfall(!wfFall.empty ? wfFall.items : []);
      } else {
        setWorkflow(null);
        setWaterfall([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent');
    } finally {
      setLoading(false);
    }
  }, [agentId, selectedExec]);

  useAutoRefresh(load, 30);

  const tokenMetrics = useMemo(() => {
    const withTokens = executions.filter((e) => e.total_tokens != null);
    if (!withTokens.length) return { total: null, avg: null, available: false };
    const total = withTokens.reduce((s, e) => s + (e.total_tokens ?? 0), 0);
    return { total, avg: total / withTokens.length, available: true };
  }, [executions]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!agent) return <EmptyState title="Agent not found" message="This agent is not in the registry." />;

  return (
    <div className="stack">
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
              <Link to="/agents">Agents</Link> / {agent.name}
            </div>
            <h2 className="panel-title" style={{ fontSize: 18 }}>
              {agent.name}
            </h2>
            <p className="panel-subtitle">
              {displayOrDash(agent.cloud)} · {displayOrDash(agent.platform)} · {displayOrDash(agent.framework)}
            </p>
          </div>
          <AgentHealthBadge health={agent.health} />
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} type="button" className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="stack">
          <div className="grid-kpi" style={{ gridTemplateColumns: 'repeat(4, minmax(0,1fr))' }}>
            <MetricCard label="Executions" value={executionCount} available={executionCount != null} />
            <MetricCard
              label="Primary Model"
              displayValue={agent.primary_model}
              subtitle={agent.primary_model ? undefined : 'No live data'}
            />
            <MetricCard
              label="Last Execution"
              displayValue={agent.last_execution_at ? formatRelative(agent.last_execution_at) : null}
              subtitle={agent.last_execution_at ? undefined : 'No live data'}
            />
            <MetricCard
              label="Last Telemetry"
              displayValue={agent.last_telemetry_at ? formatRelative(agent.last_telemetry_at) : null}
              subtitle={agent.last_telemetry_at ? undefined : 'No live data'}
            />
          </div>
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Registry</h3>
            </div>
            <dl className="dl-grid">
              <dt>Environment</dt>
              <dd>{displayOrDash(agent.environment)}</dd>
              <dt>Region</dt>
              <dd>{displayOrDash(agent.region)}</dd>
              <dt>Owner</dt>
              <dd>{displayOrDash(agent.owner)}</dd>
              <dt>Business Unit</dt>
              <dd>{displayOrDash(agent.business_unit)}</dd>
              <dt>Integration</dt>
              <dd>{displayOrDash(agent.integration_id)}</dd>
              <dt>Telemetry Source</dt>
              <dd>{displayOrDash(agent.telemetry_source)}</dd>
            </dl>
          </div>
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Telemetry Quality</h3>
            </div>
            {quality ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {Object.entries(quality).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className="muted" style={{ fontSize: 11 }}>
                      {k.replace(/_/g, ' ')}
                    </span>
                    <TelemetryQualityBadge quality={v} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No quality assessment" message="Quality dimensions appear after executions." compact />
            )}
          </div>
        </div>
      )}

      {tab === 'Live Executions' && (
        <div className="panel">
          {live.length === 0 ? (
            <EmptyState title="No live executions" message="Running executions for this agent will appear here." />
          ) : (
            <ExecTable rows={live} selected={selectedExec} onSelect={setSelectedExec} />
          )}
        </div>
      )}

      {tab === 'Workflow' && (
        <div className="stack">
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Workflow Graph</h3>
              {executions.length > 0 ? (
                <select
                  className="select"
                  value={selectedExec ?? ''}
                  onChange={(e) => setSelectedExec(e.target.value || null)}
                >
                  {executions.map((e) => (
                    <option key={e.execution_id} value={e.execution_id}>
                      {e.execution_id.slice(0, 12)}… · {e.status}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
            <WorkflowGraph graph={workflow} />
          </div>
          <div className="panel">
            <div className="panel-header">
              <h3 className="panel-title">Waterfall</h3>
            </div>
            <ExecutionWaterfall items={waterfall} />
          </div>
        </div>
      )}

      {tab === 'Executions' && (
        <div className="panel">
          {executions.length === 0 ? (
            <EmptyState title="No executions received" message="Executions appear when live telemetry spans are ingested." />
          ) : (
            <ExecTable rows={executions} selected={selectedExec} onSelect={setSelectedExec} />
          )}
        </div>
      )}

      {tab === 'Tokens' && (
        <div className="grid-kpi" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <MetricCard label="Total Tokens" value={tokenMetrics.total} available={tokenMetrics.available} />
          <MetricCard label="Avg Tokens / Exec" value={tokenMetrics.avg} available={tokenMetrics.available} />
          <MetricCard
            label="Input Tokens (latest)"
            value={executions[0]?.input_tokens ?? null}
            available={executions[0]?.input_tokens != null}
          />
        </div>
      )}

      {tab === 'Models' && (
        <div className="panel">
          <dl className="dl-grid">
            <dt>Primary</dt>
            <dd>{displayOrDash(agent.primary_model)}</dd>
            <dt>Fallback</dt>
            <dd>{displayOrDash(agent.fallback_model)}</dd>
            <dt>Latest in exec</dt>
            <dd>{displayOrDash(executions[0]?.model_name)}</dd>
          </dl>
        </div>
      )}

      {tab === 'Steps' && (
        <MetricStrip
          items={executions.map((e) => ({
            id: e.execution_id,
            label: e.execution_id.slice(0, 10),
            value: e.agent_steps,
          }))}
          empty="No step counts in telemetry"
        />
      )}

      {tab === 'Tools' && (
        <MetricStrip
          items={executions.map((e) => ({
            id: e.execution_id,
            label: e.execution_id.slice(0, 10),
            value: e.tool_calls,
          }))}
          empty="No tool call telemetry"
        />
      )}

      {tab === 'MCP' && (
        <MetricStrip
          items={executions.map((e) => ({
            id: e.execution_id,
            label: e.execution_id.slice(0, 10),
            value: e.mcp_calls,
          }))}
          empty="No MCP telemetry"
        />
      )}

      {tab === 'RAG' && (
        <MetricStrip
          items={executions.map((e) => ({
            id: e.execution_id,
            label: e.execution_id.slice(0, 10),
            value: e.rag_queries,
          }))}
          empty="No RAG telemetry"
        />
      )}

      {tab === 'A2A' && (
        <MetricStrip
          items={executions.map((e) => ({
            id: e.execution_id,
            label: e.execution_id.slice(0, 10),
            value: e.a2a_calls,
          }))}
          empty="No A2A telemetry"
        />
      )}

      {tab === 'Tracing' && (
        <div className="panel">
          <TraceExplorer traces={traces} />
        </div>
      )}

      {tab === 'Performance' && (
        <div className="grid-kpi" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <MetricCard
            label="Avg Duration"
            value={
              executions.some((e) => e.execution_duration_ms != null)
                ? executions.filter((e) => e.execution_duration_ms != null).reduce((s, e) => s + (e.execution_duration_ms ?? 0), 0) /
                  executions.filter((e) => e.execution_duration_ms != null).length
                : null
            }
            available={executions.some((e) => e.execution_duration_ms != null)}
            format="duration"
          />
          <MetricCard
            label="Retries (latest)"
            value={executions[0]?.retry_count ?? null}
            available={executions[0]?.retry_count != null}
          />
          <MetricCard
            label="Fallbacks (latest)"
            value={executions[0]?.fallback_count ?? null}
            available={executions[0]?.fallback_count != null}
          />
        </div>
      )}

      {tab === 'Errors' && (
        <div className="panel">
          {executions.filter((e) => e.status === 'failed' || (e.error_count ?? 0) > 0).length === 0 ? (
            <EmptyState title="No errors recorded" message="Failed executions with telemetry will list here." />
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Execution</th>
                    <th>Status</th>
                    <th>Error Type</th>
                    <th>Errors</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {executions
                    .filter((e) => e.status === 'failed' || (e.error_count ?? 0) > 0)
                    .map((e) => (
                      <tr key={e.execution_id}>
                        <td className="mono">{e.execution_id.slice(0, 14)}</td>
                        <td>{e.status}</td>
                        <td>{displayOrDash(e.error_type)}</td>
                        <td className="mono">{formatNumber(e.error_count)}</td>
                        <td className="mono">{formatTimestamp(e.start_time ?? e.timestamp)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'Integrations' && (
        <div className="panel">
          <dl className="dl-grid">
            <dt>Integration ID</dt>
            <dd>{displayOrDash(agent.integration_id)}</dd>
            <dt>Telemetry Source</dt>
            <dd>{displayOrDash(agent.telemetry_source)}</dd>
            <dt>Endpoint Ref</dt>
            <dd>{displayOrDash(agent.endpoint_ref)}</dd>
          </dl>
        </div>
      )}

      {tab === 'Optimization' && (
        <div className="panel">
          {efficiency ? (
            <div className="muted" style={{ marginBottom: 12, fontSize: 12 }}>
              Efficiency payload present from API
            </div>
          ) : null}
          <OptimizationPanel items={optimization} />
        </div>
      )}
    </div>
  );
}

function ExecTable({
  rows,
  selected,
  onSelect,
}: {
  rows: Execution[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Execution</th>
            <th>Status</th>
            <th>Model</th>
            <th>Tokens</th>
            <th>Duration</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr
              key={e.execution_id}
              style={{ cursor: 'pointer', background: selected === e.execution_id ? 'var(--bg-hover)' : undefined }}
              onClick={() => onSelect(e.execution_id)}
            >
              <td className="mono">{e.execution_id.slice(0, 16)}</td>
              <td>{e.status}</td>
              <td className="mono">{displayOrDash(e.model_name)}</td>
              <td className="mono">{formatNumber(e.total_tokens)}</td>
              <td className="mono">{formatDuration(e.execution_duration_ms)}</td>
              <td className="mono">{formatTimestamp(e.start_time ?? e.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricStrip({
  items,
  empty,
}: {
  items: Array<{ id: string; label: string; value: number | null | undefined }>;
  empty: string;
}) {
  const known = items.filter((i) => i.value != null);
  if (!known.length) return <EmptyState title={empty} message="No live data" />;
  return (
    <div className="data-table-wrap panel">
      <table className="data-table">
        <thead>
          <tr>
            <th>Execution</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.id}>
              <td className="mono">{i.label}</td>
              <td className="mono">{formatNumber(i.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
