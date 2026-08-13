import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Integration } from '../types';
import { displayOrDash, formatRelative, statusTone } from '../utils/format';
import { AzureResourceGroupField } from './AzureResourceGroupField';
import { IntegrationSwitch } from './IntegrationSwitch';

interface IntegrationCardProps {
  integration: Integration;
  onToggle: (enabled: boolean) => void;
  onConfigure: () => void;
  onDiscover?: (resourceGroup?: string) => void;
  onConfigUpdated?: () => void;
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
  onConfigUpdated,
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
  const [resourceGroup, setResourceGroup] = useState(savedRg == null ? '' : String(savedRg));
  const [savingRg, setSavingRg] = useState(false);

  useEffect(() => {
    setResourceGroup(savedRg == null ? '' : String(savedRg));
  }, [savedRg]);

  const handleResourceGroupChange = async (value: string) => {
    setResourceGroup(value);
    if (!isAzureIntegration(integration) || !integration.configured) return;
    setSavingRg(true);
    try {
      await api.saveIntegrationConfig(integration.id, {
        fields: {
          ...integration.config.fields,
          resource_group: value,
        },
        auth_method: integration.config.auth_method ?? null,
      });
      onConfigUpdated?.();
    } finally {
      setSavingRg(false);
    }
  };

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

      {isAzureIntegration(integration) && integration.configured ? (
        <AzureResourceGroupField
          integrationId={integration.id}
          value={resourceGroup}
          onChange={(value) => void handleResourceGroupChange(value)}
          disabled={savingRg || discovering}
          showLoadButton={false}
          label="Resource group"
          helpText={
            savingRg
              ? 'Saving selection…'
              : 'Select a resource group — the value is saved immediately and used for discovery.'
          }
        />
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
            disabled={discovering || savingRg}
          >
            {discovering ? 'Discovering…' : 'Refresh Discovery'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
