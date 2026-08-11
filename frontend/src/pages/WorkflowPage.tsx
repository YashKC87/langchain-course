import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { Execution, WaterfallItem, WorkflowGraph as WFGraph } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { ExecutionWaterfall } from '../components/ExecutionWaterfall';
import { LoadingState } from '../components/LoadingState';
import { WorkflowGraph } from '../components/WorkflowGraph';
import { displayOrDash, formatTimestamp } from '../utils/format';

export function WorkflowPage() {
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [graph, setGraph] = useState<WFGraph | null>(null);
  const [waterfall, setWaterfall] = useState<WaterfallItem[]>([]);
  const [emptyList, setEmptyList] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGraph = useCallback(async (executionId: string) => {
    if (!executionId) {
      setGraph(null);
      setWaterfall([]);
      return;
    }
    const [wf, fall] = await Promise.all([
      api.getExecutionWorkflow(executionId),
      api.getExecutionWaterfall(executionId),
    ]);
    setGraph(wf);
    setWaterfall(!fall.empty ? fall.items : []);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getExecutions();
      if (res.empty) {
        setEmptyList({ title: res.title ?? 'No executions received', message: res.message ?? 'No live data' });
        setExecutions([]);
        setSelected('');
        setGraph(null);
        setWaterfall([]);
      } else {
        setEmptyList(null);
        setExecutions(res.items);
        const id =
          selected && res.items.some((e) => e.execution_id === selected)
            ? selected
            : res.items[0].execution_id;
        setSelected(id);
        await loadGraph(id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflow');
    } finally {
      setLoading(false);
    }
  }, [selected, loadGraph]);

  useAutoRefresh(load, 30);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Execution Workflow</h2>
            <p className="panel-subtitle">
              Select an execution to inspect the live graphical path and waterfall
            </p>
          </div>
          {executions.length > 0 ? (
            <select
              className="select"
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                void loadGraph(e.target.value);
              }}
              style={{ minWidth: 280 }}
            >
              {executions.map((e) => (
                <option key={e.execution_id} value={e.execution_id}>
                  {displayOrDash(e.agent_name)} · {e.execution_id.slice(0, 12)} · {e.status} ·{' '}
                  {formatTimestamp(e.start_time ?? e.timestamp)}
                </option>
              ))}
            </select>
          ) : null}
        </div>
        {emptyList ? (
          <EmptyState title={emptyList.title} message={emptyList.message} />
        ) : (
          <WorkflowGraph graph={graph} height={460} />
        )}
      </div>
      {!emptyList ? (
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Execution Waterfall</h2>
          </div>
          <ExecutionWaterfall items={waterfall} />
        </div>
      ) : null}
    </div>
  );
}
