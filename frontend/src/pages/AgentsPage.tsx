import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { AgentMeteringRow } from '../types';
import { AgentTable } from '../components/AgentTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';

export function AgentsPage() {
  const [rows, setRows] = useState<AgentMeteringRow[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getAgentMetering();
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No agents discovered', message: res.message ?? 'No live data' });
        setRows([]);
      } else {
        setEmpty(null);
        setRows(res.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Agent Metering</h2>
          <p className="panel-subtitle">Live operational metering across discovered agents</p>
        </div>
      </div>
      {empty ? (
        <EmptyState title={empty.title} message={empty.message} />
      ) : (
        <AgentTable rows={rows} />
      )}
    </div>
  );
}
