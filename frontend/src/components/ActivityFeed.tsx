import type { ActivityEvent } from '../types';
import { formatRelative } from '../utils/format';
import { EmptyState } from './EmptyState';

interface ActivityFeedProps {
  items: ActivityEvent[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function ActivityFeed({
  items,
  emptyTitle = 'No live activity',
  emptyMessage = 'Activity events appear when telemetry is ingested.',
}: ActivityFeedProps) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  return (
    <div className="feed-list">
      {items.map((event) => (
        <div className="feed-item" key={event.id}>
          <div className={`feed-dot ${event.severity}`} />
          <div>
            <div className="feed-msg">{event.message}</div>
            <div className="feed-meta">
              {event.event_type}
              {event.agent_name ? ` · ${event.agent_name}` : ''}
            </div>
          </div>
          <div className="feed-time">{formatRelative(event.timestamp)}</div>
        </div>
      ))}
    </div>
  );
}
