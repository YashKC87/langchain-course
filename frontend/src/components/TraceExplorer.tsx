import { useState } from 'react';
import type { TraceSummary } from '../types';
import { api } from '../api/client';
import { formatRelative, formatTimestamp } from '../utils/format';
import { EmptyState } from './EmptyState';
import { LoadingState } from './LoadingState';

interface TraceExplorerProps {
  traces: TraceSummary[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function TraceExplorer({
  traces,
  emptyTitle = 'No matching traces',
  emptyMessage = 'Traces appear when OpenTelemetry spans are ingested.',
}: TraceExplorerProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [spans, setSpans] = useState<Array<Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openTrace = async (traceId: string) => {
    setSelected(traceId);
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTrace(traceId);
      setSpans(data.spans);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trace');
      setSpans(null);
    } finally {
      setLoading(false);
    }
  };

  if (!traces.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  return (
    <div className="grid-2">
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Trace ID</th>
              <th>Root</th>
              <th>Spans</th>
              <th>Start</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((t) => (
              <tr
                key={t.trace_id}
                style={{ cursor: 'pointer', background: selected === t.trace_id ? 'var(--bg-hover)' : undefined }}
                onClick={() => void openTrace(t.trace_id)}
              >
                <td className="mono">{t.trace_id.slice(0, 16)}…</td>
                <td>{t.root_name ?? '—'}</td>
                <td className="mono">{t.span_count}</td>
                <td className="mono">{formatRelative(t.start_time)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <div className="panel-header">
          <h3 className="panel-title">Span Detail</h3>
        </div>
        {!selected ? (
          <EmptyState title="Select a trace" message="Choose a trace to inspect spans." compact />
        ) : loading ? (
          <LoadingState label="Loading spans…" />
        ) : error ? (
          <EmptyState title="Trace unavailable" message={error} compact />
        ) : spans && spans.length ? (
          <div className="feed-list">
            {spans.map((s) => (
              <div className="feed-item" key={String(s.span_id)}>
                <div className="feed-dot info" />
                <div>
                  <div className="feed-msg">{String(s.name ?? 'span')}</div>
                  <div className="feed-meta mono">
                    {String(s.node_type ?? 'unknown')} · {String(s.status ?? '—')} ·{' '}
                    {s.duration_ms != null ? `${s.duration_ms}ms` : '—'}
                  </div>
                </div>
                <div className="feed-time">{formatTimestamp(s.start_time as string | null)}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No spans" message="Trace has no span payload." compact />
        )}
      </div>
    </div>
  );
}
