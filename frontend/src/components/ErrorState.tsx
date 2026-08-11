import { AlertTriangle } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = 'Unable to load data', message, onRetry }: ErrorStateProps) {
  return (
    <div className="state-box">
      <AlertTriangle size={28} color="var(--status-failed)" strokeWidth={1.5} />
      <h3>{title}</h3>
      <p>{message}</p>
      {onRetry ? (
        <div className="state-actions">
          <button type="button" className="btn" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}
