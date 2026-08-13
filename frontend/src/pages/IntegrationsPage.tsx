import { useCallback, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api, formatApiError } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { Integration } from '../types';
import { ConnectionWizard } from '../components/ConnectionWizard';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { IntegrationCard } from '../components/IntegrationCard';
import { LoadingState } from '../components/LoadingState';
import { categoryLabel } from '../utils/format';

const CATEGORY_ORDER = [
  'cloud_platforms',
  'agent_platforms',
  'observability',
  'enterprise_tools',
  'protocols',
  'rag_data_sources',
];

export function IntegrationsPage() {
  const location = useLocation();
  const focusId = (location.state as { focus?: string } | null)?.focus;
  const [groups, setGroups] = useState<Record<string, Integration[]>>({});
  const [configure, setConfigure] = useState<Integration | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState<string | null>(null);
  const [progressNote, setProgressNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getIntegrations();
      setGroups(res.groups ?? {});
      if (focusId && !configure) {
        const all = Object.values(res.groups ?? {}).flat();
        const match =
          all.find((i) => i.id === focusId) ||
          all.find((i) => i.provider === focusId) ||
          all.find((i) => i.id.startsWith(focusId));
        if (match) setConfigure(match);
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [focusId, configure]);

  useAutoRefresh(load, 60);

  const orderedKeys = useMemo(() => {
    const keys = Object.keys(groups);
    return [
      ...CATEGORY_ORDER.filter((k) => keys.includes(k)),
      ...keys.filter((k) => !CATEGORY_ORDER.includes(k)),
    ];
  }, [groups]);

  const onToggle = async (integration: Integration, enabled: boolean) => {
    setToggling(integration.id);
    setProgressNote(null);
    try {
      const updated = await api.toggleIntegration(integration.id, enabled);
      if (enabled) {
        setConfigure(updated);
        setProgressNote(
          updated.enable_progress?.some((s) => s.status === 'failed')
            ? 'Enable workflow completed with failures — review stages.'
            : 'Enable workflow finished.',
        );
      } else {
        setProgressNote('Integration Disabled / Historical telemetry retained');
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Toggle failed');
    } finally {
      setToggling(null);
    }
  };

  const onDiscover = async (integration: Integration) => {
    setDiscovering(integration.id);
    setProgressNote(null);
    try {
      const result = await api.discoverIntegration(integration.id);
      const count = result.counts?.total ?? result.agents?.length ?? 0;
      if (result.ok) {
        const scope =
          result.subscription_id != null
            ? `subscription ${result.subscription_id}`
            : result.account_id != null
              ? `account ${result.account_id}`
              : '';
        setProgressNote(
          result.message ||
            (count
              ? `Discovered ${count} agent(s)${scope ? ` in ${scope}` : ''}.`
              : 'Discovery finished — no agents found.'),
        );
      } else {
        setProgressNote(result.message || 'Discovery failed.');
      }
      await load();
    } catch (err) {
      setProgressNote(err instanceof Error ? err.message : 'Discovery failed');
    } finally {
      setDiscovering(null);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  if (!orderedKeys.length) {
    return (
      <EmptyState
        title="Connect Your First Platform"
        message="No integration catalog returned from the API."
      />
    );
  }

  return (
    <div className="stack">
      {progressNote ? <div className="disabled-banner">{progressNote}</div> : null}
      {orderedKeys.map((key) => (
        <div key={key} className="panel">
          <div className="panel-header">
            <h2 className="panel-title">{categoryLabel(key)}</h2>
          </div>
          <div className="integration-grid">
            {groups[key].map((integ) => (
              <IntegrationCard
                key={integ.id}
                integration={integ}
                toggling={toggling === integ.id}
                discovering={discovering === integ.id}
                onConfigure={() => setConfigure(integ)}
                onToggle={(on) => void onToggle(integ, on)}
                onDiscover={() => void onDiscover(integ)}
              />
            ))}
          </div>
        </div>
      ))}

      {configure ? (
        <ConnectionWizard
          integration={configure}
          open
          onClose={() => setConfigure(null)}
          onSaved={(updated) => {
            setConfigure(updated);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
