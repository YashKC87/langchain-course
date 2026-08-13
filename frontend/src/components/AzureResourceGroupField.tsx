import { useEffect, useState } from 'react';
import { api } from '../api/client';

export interface AzureResourceGroupOption {
  name: string;
  location?: string;
}

interface AzureResourceGroupFieldProps {
  integrationId: string;
  value: string;
  onChange: (value: string) => void;
  /** When set (Configure wizard), list RGs using unsaved form values. */
  draftFields?: Record<string, string>;
  authMethod?: string;
  disabled?: boolean;
  showLoadButton?: boolean;
  label?: string;
  helpText?: string;
}

export function AzureResourceGroupField({
  integrationId,
  value,
  onChange,
  draftFields,
  disabled,
  showLoadButton = true,
  label = 'Resource Group (discovery scope)',
  helpText,
}: AzureResourceGroupFieldProps) {
  const [resourceGroups, setResourceGroups] = useState<AzureResourceGroupOption[]>([]);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const subscriptionId = draftFields?.subscription_id?.trim() ?? '';
  const draftKey = draftFields
    ? `${draftFields.subscription_id ?? ''}|${draftFields.tenant_id ?? ''}|${draftFields.client_id ?? ''}`
    : 'saved-config';

  const loadResourceGroups = async () => {
    if (draftFields && !subscriptionId) {
      setResourceGroups([]);
      setLoadError('Enter Subscription ID before loading resource groups.');
      return;
    }

    setLoadingGroups(true);
    setLoadError(null);
    try {
      const fields: Record<string, unknown> = {};
      if (draftFields) {
        for (const [k, v] of Object.entries(draftFields)) {
          if (v.trim()) fields[k] = v.trim();
        }
      }
      const result = await api.listAzureResourceGroups(
        integrationId,
        Object.keys(fields).length ? fields : undefined,
      );
      if (!result.ok) {
        setLoadError(result.message || 'Unable to load resource groups.');
        return;
      }
      setResourceGroups(result.resource_groups ?? []);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load resource groups');
    } finally {
      setLoadingGroups(false);
    }
  };

  useEffect(() => {
    if (draftFields && !subscriptionId) {
      setResourceGroups([]);
      return;
    }
    void loadResourceGroups();
    // Reload when subscription/credentials change, or when using saved config on card open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [integrationId, draftKey]);

  const selectedLabel = value
    ? resourceGroups.find((g) => g.name === value)?.name ?? value
    : 'All resource groups';

  return (
    <div className="field" style={{ gridColumn: showLoadButton ? '1 / -1' : undefined }}>
      <label className="label" htmlFor={`${integrationId}-resource-group`}>
        {label}
      </label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          id={`${integrationId}-resource-group`}
          className="select"
          style={{ flex: '1 1 220px' }}
          value={value}
          disabled={disabled || loadingGroups}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">All resource groups (full subscription scan)</option>
          {value && !resourceGroups.some((g) => g.name === value) ? (
            <option value={value}>{value}</option>
          ) : null}
          {resourceGroups.map((g) => (
            <option key={g.name} value={g.name}>
              {g.name}
              {g.location ? ` (${g.location})` : ''}
            </option>
          ))}
        </select>
        {showLoadButton ? (
          <button
            type="button"
            className="btn"
            onClick={() => void loadResourceGroups()}
            disabled={loadingGroups || Boolean(draftFields && !subscriptionId) || disabled}
          >
            {loadingGroups ? 'Loading…' : 'Refresh list'}
          </button>
        ) : null}
      </div>
      <p className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        {helpText ??
          (loadingGroups
            ? 'Loading resource groups from Azure…'
            : `Selected: ${selectedLabel}${resourceGroups.length ? ` · ${resourceGroups.length} available` : ''}`)}
      </p>
      {loadError ? (
        <p className="muted" style={{ fontSize: 11, marginTop: 4, color: 'var(--status-failed)' }}>
          {loadError}
        </p>
      ) : null}
    </div>
  );
}
