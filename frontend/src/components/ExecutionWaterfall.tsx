import type { WaterfallItem } from '../types';
import { formatDuration, statusTone } from '../utils/format';
import { EmptyState } from './EmptyState';

interface ExecutionWaterfallProps {
  items: WaterfallItem[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function ExecutionWaterfall({
  items,
  emptyTitle = 'No matching traces',
  emptyMessage = 'No spans available for this execution.',
}: ExecutionWaterfallProps) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  const maxEnd = Math.max(...items.map((i) => i.start_offset_ms + Math.max(i.duration_ms, 1)), 1);

  return (
    <div className="waterfall">
      {items.map((item) => {
        const left = (item.start_offset_ms / maxEnd) * 100;
        const width = Math.max((Math.max(item.duration_ms, 1) / maxEnd) * 100, 0.4);
        const tone = statusTone(item.status);
        return (
          <div className="waterfall-row" key={item.span_id}>
            <div className="waterfall-label" title={item.name} style={{ paddingLeft: (item.depth ?? 0) * 8 }}>
              {item.name}
            </div>
            <div className="waterfall-track">
              <div
                className={`waterfall-bar ${tone}`}
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`${item.name}: ${formatDuration(item.duration_ms)}`}
              />
            </div>
            <div className="waterfall-dur">{formatDuration(item.duration_ms)}</div>
          </div>
        );
      })}
    </div>
  );
}
