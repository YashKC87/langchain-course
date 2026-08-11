import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { IntegrationHealthItem, TraceSummary } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { TelemetryQualityBadge } from '../components/TelemetryQualityBadge';
import { TraceExplorer } from '../components/TraceExplorer';
import { formatRelative, statusTone } from '../utils/format';

export function ObservabilityPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [tracesEmpty, setTracesEmpty] = useState<{ title: string; message: string } | null>(null);
  const [health, setHealth] = useState<IntegrationHealthItem[]>([]);
  const [cloud, setCloud] = useState<{ empty: boolean; title?: string; message?: string; distribution?: Record<string, number> } | null>(null);
  const [frameworks, setFrameworks] = useState<{ empty: boolean; title?: string; message?: string; distribution?: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [tr, healthRes, cloudRes, fwRes] = await Promise.all([
        api.getTraces(),
        api.getIntegrationHealth(),
        api.getCloudAnalytics(),
        api.getFrameworkAnalytics(),
      ]);
      if (tr.empty) {
        setTracesEmpty({ title: tr.title ?? 'No matching traces', message: tr.message ?? 'No live data' });
        setTraces([]);
      } else {
        setTracesEmpty(null);
        setTraces(tr.items);
      }
      setHealth(healthRes.items ?? []);
      setCloud(cloudRes);
      setFrameworks(fwRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load observability');
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Traces</h2>
        </div>
        {tracesEmpty ? (
          <EmptyState title={tracesEmpty.title} message={tracesEmpty.message} />
        ) : (
          <TraceExplorer traces={traces} />
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Metrics Quality</h2>
            <p className="panel-subtitle">Distribution analytics from live telemetry only</p>
          </div>
          {cloud?.empty && frameworks?.empty ? (
            <EmptyState
              title={cloud.title ?? 'No Live Telemetry Available'}
              message={cloud.message ?? 'Quality distributions appear when telemetry is ingested.'}
            />
          ) : (
            <div className="stack" style={{ gap: 16 }}>
              <div>
                <div className="metric-label">Cloud distribution</div>
                {cloud?.empty || !cloud?.distribution || !Object.keys(cloud.distribution).length ? (
                  <div className="muted" style={{ marginTop: 6 }}>
                    —
                  </div>
                ) : (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>
                    {Object.entries(cloud.distribution).map(([k, v]) => (
                      <li key={k} className="mono">
                        {k}: {v}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="metric-label">Framework distribution</div>
                {frameworks?.empty || !frameworks?.distribution || !Object.keys(frameworks.distribution).length ? (
                  <div className="muted" style={{ marginTop: 6 }}>
                    —
                  </div>
                ) : (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>
                    {Object.entries(frameworks.distribution).map(([k, v]) => (
                      <li key={k} className="mono">
                        {k}: {v}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <TelemetryQualityBadge quality="complete" />
                <TelemetryQualityBadge quality="partial" />
                <TelemetryQualityBadge quality="missing" />
                <TelemetryQualityBadge quality="not_provided" />
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Integration Health</h2>
          </div>
          {health.length === 0 ? (
            <EmptyState title="Integration Required" message="Connect platforms to view health." compact />
          ) : (
            <div className="feed-list">
              {health.map((h) => (
                <div className="feed-item" key={h.id}>
                  <div className={`feed-dot ${statusTone(h.status)}`} />
                  <div>
                    <div className="feed-msg">{h.name}</div>
                    <div className="feed-meta">
                      <span className={`badge ${statusTone(h.status)}`}>{h.status.replace(/_/g, ' ')}</span>
                      {h.error_message ? ` · ${h.error_message}` : ''}
                    </div>
                  </div>
                  <div className="feed-time">{formatRelative(h.last_telemetry_at)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
