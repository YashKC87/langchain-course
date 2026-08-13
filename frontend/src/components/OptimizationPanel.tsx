import type { OptimizationFinding } from '../types';
import { formatPercent, formatRelative } from '../utils/format';
import { EmptyState } from './EmptyState';

interface OptimizationPanelProps {
  items: OptimizationFinding[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function OptimizationPanel({
  items,
  emptyTitle = 'No optimization findings',
  emptyMessage = 'Recommendations appear when enough live telemetry establishes evidence and baselines.',
}: OptimizationPanelProps) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  return (
    <div className="stack" style={{ gap: 10 }}>
      {items.map((item) => (
        <div key={item.id} className="panel" style={{ padding: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
            <span className={`badge ${item.severity === 'critical' ? 'failed' : item.severity}`}>
              {item.severity}
            </span>
            <span className="muted mono" style={{ fontSize: 11 }}>
              confidence {formatPercent(item.confidence * 100)}
            </span>
          </div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{item.observation}</div>
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 6 }}>
            Evidence: {item.evidence}
          </div>
          <div style={{ fontSize: 12.5 }}>Recommendation: {item.recommendation}</div>
          <div className="feed-meta" style={{ marginTop: 6 }}>
            {item.affected_agent ?? '—'}
            {item.affected_component ? ` · ${item.affected_component}` : ''}
            {' · '}
            {formatRelative(item.detected_at)}
          </div>
        </div>
      ))}
    </div>
  );
}
