import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { A2ASummary } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatRelative,
} from '../utils/format';

export function A2APage() {
  const [items, setItems] = useState<A2ASummary[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getA2A();
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No A2A activity', message: res.message ?? 'No live data' });
        setItems([]);
      } else {
        setEmpty(null);
        setItems(res.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load A2A');
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
          <h2 className="panel-title">Multi-Agent / A2A</h2>
          <p className="panel-subtitle">Handoffs and agent-to-agent calls from live telemetry</p>
        </div>
      </div>
      {empty ? (
        <EmptyState title={empty.title} message={empty.message} />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Destination</th>
                <th>Protocol</th>
                <th>Handoffs</th>
                <th>Success</th>
                <th>Failure</th>
                <th>Avg Latency</th>
                <th>Tokens</th>
                <th>Retries</th>
                <th>Last Activity</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={`${a.source_agent}-${a.destination_agent}`}>
                  <td>{a.source_agent}</td>
                  <td>{a.destination_agent}</td>
                  <td>{displayOrDash(a.protocol)}</td>
                  <td className="mono">{formatNumber(a.handoffs)}</td>
                  <td className="mono">{formatNumber(a.success)}</td>
                  <td className="mono">{formatNumber(a.failure)}</td>
                  <td className="mono">{formatDuration(a.average_latency_ms)}</td>
                  <td className="mono">{formatNumber(a.tokens)}</td>
                  <td className="mono">{formatNumber(a.retries)}</td>
                  <td className="mono">{formatRelative(a.last_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
