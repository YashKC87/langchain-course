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

function pickRunningExecution(items: Execution[], preferredId?: string | null): Execution | null {
  const running = items.filter((e) => e.status === 'running');
  if (!running.length) return null;
  if (preferredId && running.some((e) => e.execution_id === preferredId)) {
    return running.find((e) => e.execution_id === preferredId) ?? null;
  }
  return [...running].sort((a, b) => {
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

export function LiveExecutionsPage() {
  const [items, setItems] = useState<Execution[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [graph, setGraph] = useState<WFGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningOnlyWorkflow, setRunningOnlyWorkflow] = useState(true);

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
      const res = await api.getExecutions({ live_only: true });
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No executions received', message: res.message ?? 'No live data' });
        setItems([]);
        setGraph(null);
        setSelected(null);
      } else {
        setEmpty(null);
        setItems(res.items);
        const running = pickRunningExecution(res.items, selected);
        if (runningOnlyWorkflow) {
          const id = running?.execution_id ?? null;
          setSelected(id);
          await loadGraph(id);
        } else {
          const id =
            selected && res.items.some((e) => e.execution_id === selected)
              ? selected
              : running?.execution_id ?? res.items[0].execution_id;
          setSelected(id);
          await loadGraph(id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load live executions');
    } finally {
      setLoading(false);
    }
  }, [selected, runningOnlyWorkflow, loadGraph]);

  useAutoRefresh(load, 30);

  const selectExecution = (execution: Execution) => {
    if (runningOnlyWorkflow && execution.status !== 'running') return;
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
                ? `${runningCount} currently running · select a tile to inspect`
                : 'No agent is running right now'}
            </p>
          </div>
          <label className="muted" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={runningOnlyWorkflow}
              onChange={(e) => setRunningOnlyWorkflow(e.target.checked)}
            />
            Workflow: running only
          </label>
        </div>
        {empty ? (
          <EmptyState title={empty.title} message={empty.message} />
        ) : (
          <div className="execution-tile-list">
            {items.map((e) => {
              const isRunning = e.status === 'running';
              const disabled = runningOnlyWorkflow && !isRunning;
              return (
                <SectionTile
                  key={e.execution_id}
                  title={displayOrDash(e.agent_name)}
                  description={`${e.execution_id.slice(0, 18)}…`}
                  value={formatNumber(e.total_tokens)}
                  tone={tileTone(e.status)}
                  selected={selected === e.execution_id}
                  onClick={disabled ? undefined : () => selectExecution(e)}
                  meta={
                    <>
                      <span className={`badge ${statusTone(e.status)}`}>{e.status}</span>
                      <span>{formatTimestamp(e.start_time ?? e.timestamp)}</span>
                      <span>{formatDuration(e.execution_duration_ms)}</span>
                      {disabled ? <span>Completed — workflow shows running agent only</span> : null}
                    </>
                  }
                />
              );
            })}
          </div>
        )}
      </div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Live Agent Workflow</h2>
            <p className="panel-subtitle">
              {selectedItem?.status === 'running'
                ? `${displayOrDash(selectedItem.agent_name)} · currently running · ${formatDuration(selectedItem.execution_duration_ms)}`
                : runningOnlyWorkflow
                  ? 'Showcase only the agent that is currently running'
                  : selectedItem
                    ? `${displayOrDash(selectedItem.agent_name)} · ${selectedItem.status}`
                    : 'Select an execution tile'}
            </p>
          </div>
        </div>
        {selectedItem?.status === 'running' || (!runningOnlyWorkflow && graph) ? (
          <WorkflowGraph graph={graph} highlightRunning height={480} />
        ) : (
          <EmptyState
            title="No agent currently running"
            message="Live Agent Workflow shows only the in-progress agent. Start an agent run to see the live graph."
            compact
          />
        )}
      </div>
    </div>
  );
}
