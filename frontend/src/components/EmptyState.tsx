import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ title, message, icon, actions, compact }: EmptyStateProps) {
  return (
    <div className="state-box" style={compact ? { minHeight: 100, padding: 24 } : undefined}>
      {icon ?? <Inbox size={28} strokeWidth={1.5} style={{ opacity: 0.5 }} />}
      <h3>{title}</h3>
      {message ? <p>{message}</p> : null}
      {actions ? <div className="state-actions">{actions}</div> : null}
    </div>
  );
}
