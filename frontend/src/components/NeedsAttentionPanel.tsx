import { Link } from 'react-router-dom';
import type { AttentionItem } from '../types';
import { formatRelative } from '../utils/format';
import { EmptyState } from './EmptyState';

interface NeedsAttentionPanelProps {
  items: AttentionItem[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function NeedsAttentionPanel({
  items,
  emptyTitle = 'No active warnings',
  emptyMessage = 'No telemetry-backed problems detected.',
}: NeedsAttentionPanelProps) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  return (
    <div className="feed-list">
      {items.map((item) => (
        <div className="feed-item" key={item.id}>
          <div className={`feed-dot ${item.severity}`} />
          <div>
            <div className="feed-msg">{item.message}</div>
            <div className="feed-meta">
              {item.condition.replace(/_/g, ' ')}
              {item.agent_name ? ` · ${item.agent_name}` : ''}
              {item.component ? ` · ${item.component}` : ''}
              {item.related_trace ? (
                <>
                  {' · '}
                  <Link to="/observability">trace</Link>
                </>
              ) : null}
            </div>
          </div>
          <div className="feed-time">{formatRelative(item.detected_at)}</div>
        </div>
      ))}
    </div>
  );
}
