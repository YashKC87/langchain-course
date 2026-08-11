import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { Execution, WorkflowGraph as WFGraph } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { WorkflowGraph } from '../components/WorkflowGraph';
import { displayOrDash, formatDuration, formatNumber, formatTimestamp, statusTone } from '../utils/format';

export function LiveExecutionsPage() {
  const [items, setItems] = useState<Execution[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [graph, setGraph] = useState<WFGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        const id = selected && res.items.some((e) => e.execution_id === selected)
          ? selected
          : res.items[0].execution_id;
        setSelected(id);
        setGraph(await api.getExecutionWorkflow(id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load live executions');
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useAutoRefresh(load, 30);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="grid-2">
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Running Executions</h2>
        </div>
        {empty ? (
          <EmptyState title={empty.title} message={empty.message} />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Execution</th>
                  <th>Agent</th>
                  <th>Status</th>
                  <th>Tokens</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => (
                  <tr
                    key={e.execution_id}
                    style={{
                      cursor: 'pointer',
                      background: selected === e.execution_id ? 'var(--bg-hover)' : undefined,
                    }}
                    onClick={() => setSelected(e.execution_id)}
                  >
                    <td className="mono">{e.execution_id.slice(0, 14)}</td>
                    <td>{displayOrDash(e.agent_name)}</td>
                    <td>
                      <span className={`badge ${statusTone(e.status)}`}>{e.status}</span>
                    </td>
                    <td className="mono">{formatNumber(e.total_tokens)}</td>
                    <td className="mono">{formatTimestamp(e.start_time ?? e.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Live Workflow</h2>
            <p className="panel-subtitle">
              {selected ? `Highlighting running nodes · ${formatDuration(items.find((i) => i.execution_id === selected)?.execution_duration_ms)}` : 'Select an execution'}
            </p>
          </div>
        </div>
        <WorkflowGraph graph={graph} highlightRunning height={480} />
      </div>
    </div>
  );
}
