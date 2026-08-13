import { AlertTriangle } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

function renderMessage(message: string) {
  const lines = message.split('\n');
  if (lines.length <= 1) return <p>{message}</p>;
  return (
    <div className="error-message-block">
      <p>{lines[0]}</p>
      {lines.slice(1).map((line) =>
        line.trim() ? (
          <p key={line} className="mono muted" style={{ fontSize: 12, margin: '4px 0' }}>
            {line}
          </p>
        ) : null,
      )}
    </div>
  );
}

export function ErrorState({ title = 'Unable to load data', message, onRetry }: ErrorStateProps) {
  const isApiDown = /cannot reach|failed to fetch|backend must be running/i.test(message);

  return (
    <div className="state-box">
      <AlertTriangle size={28} color="var(--status-failed)" strokeWidth={1.5} />
      <h3>{isApiDown ? 'API connection required' : title}</h3>
      {renderMessage(message)}
      {isApiDown ? (
        <p className="muted" style={{ fontSize: 12, maxWidth: 520 }}>
          This is not an Azure tenant/subscription error yet — the UI cannot talk to the backend.
          After the API is reachable, configure Microsoft Azure under Integrations with your Tenant ID
          and Subscription ID.
        </p>
      ) : null}
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
