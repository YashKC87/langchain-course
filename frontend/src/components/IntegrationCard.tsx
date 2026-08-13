import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Integration } from '../types';
import { displayOrDash, formatRelative, statusTone } from '../utils/format';
import { IntegrationSwitch } from './IntegrationSwitch';

interface IntegrationCardProps {
  integration: Integration;
  onToggle: (enabled: boolean) => void;
  onConfigure: () => void;
  onDiscover?: (resourceGroup?: string) => void;
  toggling?: boolean;
  discovering?: boolean;
}

function isAzureIntegration(integration: Integration) {
  return integration.id === 'azure' || integration.provider === 'azure';
}

export function IntegrationCard({
  integration,
  onToggle,
  onConfigure,
  onDiscover,
  toggling,
  discovering,
}: IntegrationCardProps) {
  const tone = statusTone(integration.status);
  const agents =
    integration.agents_discovered == null ? '—' : String(integration.agents_discovered);
  const canDiscover =
    Boolean(onDiscover) &&
    integration.enabled &&
    (integration.id === 'azure' ||
      integration.provider === 'azure' ||
      integration.id === 'aws' ||
      ['bedrock', 'bedrock-agents', 'agentcore'].includes(integration.id));

  const savedRg = integration.config.fields?.resource_group;
  const [resourceGroups, setResourceGroups] = useState<Array<{ name: string; location?: string }>>(
    [],
  );
  const [resourceGroup, setResourceGroup] = useState(
    savedRg == null ? '' : String(savedRg),
  );
  const [loadingGroups, setLoadingGroups] = useState(false);

  useEffect(() => {
    setResourceGroup(savedRg == null ? '' : String(savedRg));
  }, [savedRg]);

  useEffect(() => {
    if (!isAzureIntegration(integration) || !integration.enabled || !integration.configured) {
      return;
    }
    let cancelled = false;
    setLoadingGroups(true);
    void api
      .listAzureResourceGroups(integration.id)
      .then((result) => {
        if (cancelled || !result.ok) return;
        setResourceGroups(result.resource_groups ?? []);
      })
      .finally(() => {
        if (!cancelled) setLoadingGroups(false);
      });
    return () => {
      cancelled = true;
    };
  }, [integration.id, integration.enabled, integration.configured]);

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
        {isAzureIntegration(integration) && integration.configured ? (
          <>
            <dt>Discovery scope</dt>
            <dd>{resourceGroup || 'All resource groups'}</dd>
          </>
        ) : null}
      </dl>

      {integration.error_message ? (
        <div className="disabled-banner" style={{ color: 'var(--status-failed)' }}>
          {integration.error_message}
        </div>
      ) : null}

      {canDiscover && isAzureIntegration(integration) ? (
        <div className="field" style={{ marginBottom: 8 }}>
          <label className="label" htmlFor={`${integration.id}-card-rg`}>
            Resource group
          </label>
          <select
            id={`${integration.id}-card-rg`}
            className="select"
            value={resourceGroup}
            disabled={loadingGroups || discovering}
            onChange={(e) => setResourceGroup(e.target.value)}
          >
            <option value="">All resource groups</option>
            {resourceGroup && !resourceGroups.some((g) => g.name === resourceGroup) ? (
              <option value={resourceGroup}>{resourceGroup} (saved)</option>
            ) : null}
            {resourceGroups.map((g) => (
              <option key={g.name} value={g.name}>
                {g.name}
                {g.location ? ` (${g.location})` : ''}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <div className="integration-actions">
        <button type="button" className="btn" onClick={onConfigure}>
          Configure
        </button>
        {canDiscover ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onDiscover?.(resourceGroup || undefined)}
            disabled={discovering}
          >
            {discovering ? 'Discovering…' : 'Refresh Discovery'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
