import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { RAGSummary } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatRelative,
} from '../utils/format';

export function RagPage() {
  const [items, setItems] = useState<RAGSummary[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getRag();
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No RAG telemetry', message: res.message ?? 'No live data' });
        setItems([]);
      } else {
        setEmpty(null);
        setItems(res.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load RAG');
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
          <h2 className="panel-title">RAG</h2>
          <p className="panel-subtitle">Knowledge retrieval telemetry from live spans</p>
        </div>
      </div>
      {empty ? (
        <EmptyState title={empty.title} message={empty.message} />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Knowledge Source</th>
                <th>Agent</th>
                <th>Queries</th>
                <th>Search Type</th>
                <th>Documents</th>
                <th>Chunks</th>
                <th>Avg Latency</th>
                <th>Empty</th>
                <th>Failures</th>
                <th>Retries</th>
                <th>Last Query</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={`${r.knowledge_source}-${r.agent_id}`}>
                  <td>{r.knowledge_source}</td>
                  <td>{displayOrDash(r.agent_name)}</td>
                  <td className="mono">{formatNumber(r.queries)}</td>
                  <td>{displayOrDash(r.search_type)}</td>
                  <td className="mono">{formatNumber(r.documents_retrieved)}</td>
                  <td className="mono">{formatNumber(r.chunks_retrieved)}</td>
                  <td className="mono">{formatDuration(r.average_latency_ms)}</td>
                  <td className="mono">{formatNumber(r.empty_retrievals)}</td>
                  <td className="mono">{formatNumber(r.failures)}</td>
                  <td className="mono">{formatNumber(r.retries)}</td>
                  <td className="mono">{formatRelative(r.last_query)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
