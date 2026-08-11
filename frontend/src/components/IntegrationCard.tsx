import type { Integration } from '../types';
import { displayOrDash, formatRelative, statusTone } from '../utils/format';
import { IntegrationSwitch } from './IntegrationSwitch';

interface IntegrationCardProps {
  integration: Integration;
  onToggle: (enabled: boolean) => void;
  onConfigure: () => void;
  toggling?: boolean;
}

export function IntegrationCard({ integration, onToggle, onConfigure, toggling }: IntegrationCardProps) {
  const tone = statusTone(integration.status);
  const agents =
    integration.agents_discovered == null ? '—' : String(integration.agents_discovered);

  return (
    <div className="integration-card">
      <div className="integration-card-top">
        <div>
          <div className="integration-name">{integration.name}</div>
          <div className="integration-meta">
            {integration.provider} · {integration.category.replace(/_/g, ' ')}
          </div>
        </div>
        <IntegrationSwitch
          enabled={integration.enabled}
          disabled={toggling || (!integration.configured && !integration.enabled)}
          onChange={onToggle}
          ariaLabel={`${integration.name} ${integration.enabled ? 'on' : 'off'}`}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className={`badge ${tone}`}>{integration.status.replace(/_/g, ' ')}</span>
        {!integration.enabled && integration.configured ? (
          <span className="muted" style={{ fontSize: 11 }}>
            Integration Disabled / Historical telemetry retained
          </span>
        ) : null}
      </div>

      <dl className="dl-grid">
        <dt>Agents</dt>
        <dd>{agents}</dd>
        <dt>Last telemetry</dt>
        <dd>{formatRelative(integration.last_telemetry_at)}</dd>
        <dt>Health</dt>
        <dd>{displayOrDash(integration.connection_health)}</dd>
      </dl>

      {integration.error_message ? (
        <div className="disabled-banner" style={{ color: 'var(--status-failed)' }}>
          {integration.error_message}
        </div>
      ) : null}

      <div className="integration-actions">
        <button type="button" className="btn" onClick={onConfigure}>
          Configure
        </button>
      </div>
    </div>
  );
}
