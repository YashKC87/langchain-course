import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { ModelSummary } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatPercent,
  formatRelative,
} from '../utils/format';

export function ModelsPage() {
  const [items, setItems] = useState<ModelSummary[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getModels();
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No model telemetry', message: res.message ?? 'No live data' });
        setItems([]);
      } else {
        setEmpty(null);
        setItems(res.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
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
          <h2 className="panel-title">Models</h2>
          <p className="panel-subtitle">Model usage from live telemetry — missing values shown as —</p>
        </div>
      </div>
      {empty ? (
        <EmptyState title={empty.title} message={empty.message} />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Provider</th>
                <th>Cloud</th>
                <th>Agents</th>
                <th>Requests</th>
                <th>Tokens</th>
                <th>Avg Latency</th>
                <th>Success</th>
                <th>Failure</th>
                <th>Fallbacks</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.model}>
                  <td className="mono">{m.model}</td>
                  <td>{displayOrDash(m.provider)}</td>
                  <td>{displayOrDash(m.cloud)}</td>
                  <td className="mono">{formatNumber(m.agents_using)}</td>
                  <td className="mono">{formatNumber(m.requests)}</td>
                  <td className="mono">{formatNumber(m.tokens)}</td>
                  <td className="mono">{formatDuration(m.average_latency_ms)}</td>
                  <td className="mono">{formatPercent(m.success_rate)}</td>
                  <td className="mono">{formatPercent(m.failure_rate)}</td>
                  <td className="mono">{formatNumber(m.fallback_count)}</td>
                  <td className="mono">{formatRelative(m.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
