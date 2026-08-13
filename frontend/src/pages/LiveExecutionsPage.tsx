import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { Execution, WorkflowGraph as WFGraph } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { SectionTile } from '../components/SectionTile';
import { WorkflowGraph } from '../components/WorkflowGraph';
import { displayOrDash, formatDuration, formatNumber, formatTimestamp, statusTone } from '../utils/format';

function pickPreferredExecution(items: Execution[], preferredId?: string | null): Execution | null {
  if (!items.length) return null;
  if (preferredId) {
    const preferred = items.find((e) => e.execution_id === preferredId);
    if (preferred) return preferred;
  }
  const running = items.filter((e) => e.status === 'running');
  const pool = running.length ? running : items;
  return [...pool].sort((a, b) => {
    const at = a.start_time ?? a.timestamp ?? '';
    const bt = b.start_time ?? b.timestamp ?? '';
    return String(bt).localeCompare(String(at));
  })[0];
}

function tileTone(status: string): 'default' | 'running' | 'success' | 'warning' | 'failed' {
  if (status === 'running') return 'running';
  if (status === 'success') return 'success';
  if (status === 'failed' || status === 'timeout') return 'failed';
  if (status === 'warning') return 'warning';
  return 'default';
}

function statusCounts(items: Execution[]): string {
  const counts: Record<string, number> = {};
  for (const e of items) {
    counts[e.status] = (counts[e.status] ?? 0) + 1;
  }
  const order = ['running', 'success', 'failed', 'timeout', 'warning', 'cancelled', 'unknown'];
  const parts = order
    .filter((k) => counts[k])
    .map((k) => `${counts[k]} ${k}`);
  for (const [k, v] of Object.entries(counts)) {
    if (!order.includes(k)) parts.push(`${v} ${k}`);
  }
  return parts.join(' · ') || 'No transactions';
}

export function LiveExecutionsPage() {
  const [items, setItems] = useState<Execution[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [graph, setGraph] = useState<WFGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningOnlyWorkflow, setRunningOnlyWorkflow] = useState(false);

  const loadGraph = useCallback(async (executionId: string | null) => {
    if (!executionId) {
      setGraph(null);
      return;
    }
    try {
      setGraph(await api.getExecutionWorkflow(executionId));
    } catch {
      setGraph(null);
    }
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      // Prefer recent live window; fall back to all executions so completed runs remain traceable.
      let res = await api.getExecutions({ live_only: true });
      if (res.empty) {
        res = await api.getExecutions();
      }
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No executions received', message: res.message ?? 'No live data' });
        setItems([]);
        setGraph(null);
        setSelected(null);
      } else {
        setEmpty(null);
        // Show every transaction by default (running, success, failed, …).
        const list = runningOnlyWorkflow
          ? res.items.filter((e) => e.status === 'running')
          : res.items;
        if (!list.length) {
          setItems(res.items);
          setSelected(null);
          setGraph(null);
          setEmpty({
            title: 'No agent currently running',
            message: 'Turn off “Running only” to inspect all recent transactions (success, failed, and in progress).',
          });
          return;
        }
        setItems(list);
        const preferred = pickPreferredExecution(list, selected);
        const id = preferred?.execution_id ?? null;
        setSelected(id);
        await loadGraph(id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load live executions');
    } finally {
      setLoading(false);
    }
  }, [selected, runningOnlyWorkflow, loadGraph]);

  // Faster refresh so in-progress traces update while agents are still running.
  useAutoRefresh(load, 10);

  const selectExecution = (execution: Execution) => {
    setSelected(execution.execution_id);
    void loadGraph(execution.execution_id);
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  const selectedItem = items.find((i) => i.execution_id === selected) ?? null;
  const runningCount = items.filter((e) => e.status === 'running').length;

  return (
    <div className="layout-split">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Live & Recent Executions</h2>
            <p className="panel-subtitle">
              {runningCount
                ? `${runningCount} in progress · ${statusCounts(items)}`
                : `All transactions · ${statusCounts(items)}`}
            </p>
          </div>
          <label className="muted" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={runningOnlyWorkflow}
              onChange={(e) => setRunningOnlyWorkflow(e.target.checked)}
            />
            Running only
          </label>
        </div>
        {empty ? (
          <EmptyState title={empty.title} message={empty.message} />
        ) : (
          <div className="execution-tile-list">
            {items.map((e) => (
              <SectionTile
                key={e.execution_id}
                title={displayOrDash(e.agent_name)}
                description={`${e.execution_id.slice(0, 18)}…`}
                value={formatNumber(e.total_tokens)}
                tone={tileTone(e.status)}
                selected={selected === e.execution_id}
                onClick={() => selectExecution(e)}
                meta={
                  <>
                    <span className={`badge ${statusTone(e.status)}`}>{e.status}</span>
                    <span>{formatTimestamp(e.start_time ?? e.timestamp)}</span>
                    <span>{formatDuration(e.execution_duration_ms)}</span>
                  </>
                }
              />
            ))}
          </div>
        )}
      </div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Agent Workflow Trace</h2>
            <p className="panel-subtitle">
              {selectedItem
                ? `${displayOrDash(selectedItem.agent_name)} · ${selectedItem.status} · ${formatDuration(selectedItem.execution_duration_ms)}`
                : 'Select an execution tile to view the trace'}
            </p>
          </div>
        </div>
        {selectedItem && graph ? (
          <WorkflowGraph graph={graph} highlightRunning height={480} />
        ) : (
          <EmptyState
            title="No execution selected"
            message="Choose a live or recent agent run from the left to inspect its workflow and spans."
            compact
          />
        )}
      </div>
    </div>
  );
}
