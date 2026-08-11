import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AppSettings } from '../types';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';

const WEIGHT_LABELS: Record<string, string> = {
  token_efficiency: 'Token efficiency',
  latency: 'Latency',
  step_count: 'Step count',
  retry_rate: 'Retry rate',
  fallback_rate: 'Fallback rate',
  success_rate: 'Success rate',
  tool_efficiency: 'Tool efficiency',
  mcp_efficiency: 'MCP efficiency',
  rag_efficiency: 'RAG efficiency',
  a2a_efficiency: 'A2A efficiency',
  error_rate: 'Error rate',
};

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSettings(await api.getSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await api.updateSettings(settings);
      setSettings(updated);
      setMessage('Settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error && !settings) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!settings) return null;

  const num = (key: keyof AppSettings, label: string) => (
    <div className="field" key={String(key)}>
      <label className="label" htmlFor={String(key)}>
        {label}
      </label>
      <input
        id={String(key)}
        className="input"
        type="number"
        value={settings[key] as number}
        onChange={(e) =>
          setSettings({ ...settings, [key]: e.target.value === '' ? 0 : Number(e.target.value) })
        }
      />
    </div>
  );

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Thresholds & Retention</h2>
            <p className="panel-subtitle">Operational thresholds — no financial configuration</p>
          </div>
        </div>
        <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', display: 'grid' }}>
          {num('telemetry_retention_days', 'Telemetry retention (days)')}
          {num('auto_refresh_seconds', 'Auto refresh (seconds)')}
          {num('runaway_steps_warning', 'Runaway steps warning')}
          {num('runaway_steps_high', 'Runaway steps high')}
          {num('runaway_steps_critical', 'Runaway steps critical')}
          {num('runaway_retry_threshold', 'Runaway retry threshold')}
          {num('runaway_fallback_threshold', 'Runaway fallback threshold')}
          {num('runaway_duration_ms_threshold', 'Runaway duration (ms)')}
          {num('latency_warning_ms', 'Latency warning (ms)')}
          {num('latency_critical_ms', 'Latency critical (ms)')}
          {num('agent_discovery_schedule_minutes', 'Discovery schedule (min)')}
          <div className="field">
            <label className="label" htmlFor="sampling">
              Telemetry sampling rate
            </label>
            <input
              id="sampling"
              className="input"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={settings.telemetry_sampling_rate}
              onChange={(e) =>
                setSettings({ ...settings, telemetry_sampling_rate: Number(e.target.value) })
              }
            />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Content Capture</h2>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="checkbox"
            checked={settings.content_capture_enabled}
            onChange={(e) =>
              setSettings({ ...settings, content_capture_enabled: e.target.checked })
            }
          />
          <span>
            Content capture{' '}
            <strong>{settings.content_capture_enabled ? 'ON' : 'OFF'}</strong>
            <span className="muted"> — prompts/completions redacted when off</span>
          </span>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
          <input
            type="checkbox"
            checked={settings.pii_redaction_enabled}
            onChange={(e) =>
              setSettings({ ...settings, pii_redaction_enabled: e.target.checked })
            }
          />
          <span>PII redaction {settings.pii_redaction_enabled ? 'ON' : 'OFF'}</span>
        </label>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Efficiency Weights</h2>
        </div>
        <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', display: 'grid' }}>
          {Object.entries(settings.efficiency_weights).map(([key, value]) => (
            <div className="field" key={key}>
              <label className="label" htmlFor={`w-${key}`}>
                {WEIGHT_LABELS[key] ?? key}
              </label>
              <input
                id={`w-${key}`}
                className="input"
                type="number"
                step="0.005"
                min={0}
                max={1}
                value={value}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    efficiency_weights: {
                      ...settings.efficiency_weights,
                      [key]: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
          ))}
        </div>
      </div>

      {message ? <div className="disabled-banner">{message}</div> : null}
      {error ? <div className="disabled-banner" style={{ color: 'var(--status-failed)' }}>{error}</div> : null}

      <div>
        <button type="button" className="btn btn-primary" disabled={saving} onClick={() => void save()}>
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}
