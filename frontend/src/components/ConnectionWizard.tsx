import { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import type { EnableProgressStage, Integration } from '../types';
import { api } from '../api/client';

const FIELD_SCHEMAS: Record<string, Array<{ key: string; label: string; placeholder?: string }>> = {
  azure: [
    { key: 'tenant_id', label: 'Tenant ID (required)', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
    { key: 'subscription_id', label: 'Subscription ID (required)', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
    { key: 'client_id', label: 'Application (Client) ID', placeholder: 'Required for Service Principal' },
    { key: 'client_secret', label: 'Client Secret', placeholder: 'Stored as secure reference only' },
    { key: 'resource_group', label: 'Resource Group', placeholder: 'rg-agent-metering-dev' },
    { key: 'foundry_account', label: 'AI Services / Foundry Account Name', placeholder: 'Optional — scanned from subscription if empty' },
    { key: 'foundry_project', label: 'Foundry Project', placeholder: 'agent-metering-project' },
    { key: 'app_insights', label: 'Application Insights', placeholder: 'ai-agent-metering' },
    { key: 'log_analytics', label: 'Log Analytics Workspace', placeholder: 'law-agent-metering' },
    { key: 'otel_endpoint', label: 'OpenTelemetry Endpoint' },
  ],
  aws: [
    { key: 'account_id', label: 'Account ID' },
    { key: 'region', label: 'Region', placeholder: 'us-east-1' },
    { key: 'bedrock', label: 'Bedrock Endpoint / Region' },
    { key: 'agentcore', label: 'AgentCore Resource' },
    { key: 'cloudwatch', label: 'CloudWatch Log Group' },
  ],
  gcp: [
    { key: 'project_id', label: 'Project ID' },
    { key: 'region', label: 'Region', placeholder: 'us-central1' },
    { key: 'vertex_ai', label: 'Vertex AI Location' },
  ],
  otel: [
    { key: 'collector_endpoint', label: 'Collector Endpoint', placeholder: 'http://localhost:4318' },
    { key: 'protocol', label: 'Protocol', placeholder: 'http/protobuf' },
    { key: 'auth_headers', label: 'Auth Headers (header=value)' },
    { key: 'tls', label: 'TLS', placeholder: 'enabled | disabled' },
  ],
};

const SETUP_GUIDES: Record<string, { title: string; steps: string[] }> = {
  azure: {
    title: 'Connect your Azure tenant',
    steps: [
      '1. Azure Portal → Microsoft Entra ID → Overview → copy Tenant ID.',
      '2. Azure Portal → Subscriptions → copy the Subscription ID you want to monitor.',
      '3. Auth Method: Managed Identity if this app runs on Azure; otherwise Service Principal.',
      '4. Service Principal: register an app in Entra ID, grant Monitoring Reader on App Insights / Log Analytics.',
      '5. Enter Application (Client) ID and Client Secret (secret is stored as a reference, not plain text).',
      '6. Save → Test Connection → turn Microsoft Azure ON.',
      '7. Click Refresh Discovery to list agents deployed in the subscription / Foundry project.',
      '8. Agents also appear automatically when live telemetry is exported.',
    ],
  },
  aws: {
    title: 'AWS setup',
    steps: [
      'Copy the 12-digit AWS Account ID and target Region (e.g. us-east-1).',
      'Choose IAM Role or Workload Identity — avoid long-lived access keys in the UI.',
      'Save → Test → Enable. Connect Bedrock/CloudWatch telemetry via OpenTelemetry or AgentCore export.',
    ],
  },
  gcp: {
    title: 'Google Cloud setup',
    steps: [
      'Copy the GCP Project ID and region (e.g. us-central1).',
      'Use Workload Identity or Service Account with Vertex AI / Cloud Observability read access.',
      'Save → Test → Enable. Telemetry arrives via OTLP or Cloud Observability export.',
    ],
  },
  otel: {
    title: 'OpenTelemetry setup',
    steps: [
      'Point agent exporters or a collector at this Control Center ingest URL after enabling:',
      'POST /api/v1/telemetry/spans?integration_id=otel',
      'Default collector endpoint for testing: http://localhost:4318',
      'Save collector endpoint here → Test → Enable.',
    ],
  },
};

const AUTH_OPTIONS: Record<string, string[]> = {
  azure: ['Managed Identity', 'Service Principal', 'Workload Identity'],
  aws: ['IAM Role', 'IRSA', 'Access Key Ref'],
  gcp: ['Workload Identity', 'Service Account'],
  otel: ['None', 'Bearer Token', 'API Key Header'],
  default: ['API Key', 'OAuth', 'None'],
};

function schemaFor(integration: Integration) {
  if (integration.id === 'otel' || integration.provider === 'otel') return FIELD_SCHEMAS.otel;
  if (integration.provider === 'azure' || integration.id.startsWith('azure')) return FIELD_SCHEMAS.azure;
  if (integration.provider === 'aws' || ['bedrock', 'bedrock-agents', 'agentcore', 'cloudwatch'].includes(integration.id))
    return FIELD_SCHEMAS.aws;
  if (integration.provider === 'gcp' || integration.id.startsWith('vertex') || integration.id === 'gcp')
    return FIELD_SCHEMAS.gcp;
  return [
    { key: 'endpoint', label: 'Endpoint' },
    { key: 'api_endpoint', label: 'API Endpoint' },
  ];
}

function authFor(integration: Integration) {
  if (integration.id === 'otel') return AUTH_OPTIONS.otel;
  if (integration.provider === 'azure') return AUTH_OPTIONS.azure;
  if (integration.provider === 'aws') return AUTH_OPTIONS.aws;
  if (integration.provider === 'gcp') return AUTH_OPTIONS.gcp;
  return AUTH_OPTIONS.default;
}

function StageIcon({ status }: { status: string }) {
  if (status === 'success') return <>✓</>;
  if (status === 'failed') return <>✕</>;
  if (status === 'running') return <>…</>;
  return <>—</>;
}

interface ConnectionWizardProps {
  integration: Integration;
  open: boolean;
  onClose: () => void;
  onSaved: (integration: Integration) => void;
}

export function ConnectionWizard({ integration, open, onClose, onSaved }: ConnectionWizardProps) {
  const fields = useMemo(() => schemaFor(integration), [integration]);
  const authOptions = useMemo(() => authFor(integration), [integration]);
  const setupGuide = useMemo(() => {
    if (integration.id === 'otel') return SETUP_GUIDES.otel;
    if (integration.provider === 'azure' || integration.id.startsWith('azure')) return SETUP_GUIDES.azure;
    if (integration.provider === 'aws') return SETUP_GUIDES.aws;
    if (integration.provider === 'gcp') return SETUP_GUIDES.gcp;
    return null;
  }, [integration]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [authMethod, setAuthMethod] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState<EnableProgressStage[]>(integration.enable_progress ?? []);

  useEffect(() => {
    if (!open) return;
    const next: Record<string, string> = {};
    for (const f of fields) {
      const v = integration.config.fields[f.key];
      next[f.key] = v == null ? '' : String(v);
    }
    setValues(next);
    setAuthMethod(integration.config.auth_method ?? '');
    setProgress(integration.enable_progress ?? []);
    setMessage(null);
  }, [open, integration, fields]);

  if (!open) return null;

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const clean: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v.trim()) clean[k] = v.trim();
      }
      const updated = await api.saveIntegrationConfig(integration.id, {
        fields: clean,
        auth_method: authMethod || null,
      });
      onSaved(updated);
      setMessage('Configuration saved.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setMessage(null);
    try {
      const result = await api.testIntegration(integration.id);
      setMessage(result.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  return (
    <>
      <div className="side-panel-overlay" onClick={onClose} aria-hidden />
      <aside className="side-panel" role="dialog" aria-label={`Configure ${integration.name}`}>
        <div className="side-panel-header">
          <div>
            <div className="panel-title">Configure {integration.name}</div>
            <p className="panel-subtitle">Connection settings — secrets stored as references only</p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <div className="side-panel-body">
          {setupGuide ? (
            <div className="setup-guide">
              <div className="panel-title">{setupGuide.title}</div>
              <ol className="setup-guide-steps">
                {setupGuide.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          ) : null}

          <div className="form-grid">
            {fields.map((f) => (
              <div className="field" key={f.key}>
                <label className="label" htmlFor={`${integration.id}-${f.key}`}>
                  {f.label}
                </label>
                <input
                  id={`${integration.id}-${f.key}`}
                  className="input"
                  value={values[f.key] ?? ''}
                  placeholder={f.placeholder}
                  onChange={(e) => setValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="field">
              <label className="label" htmlFor={`${integration.id}-auth`}>
                Auth Method
              </label>
              <select
                id={`${integration.id}-auth`}
                className="select"
                value={authMethod}
                onChange={(e) => setAuthMethod(e.target.value)}
              >
                <option value="">Select…</option>
                {authOptions.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {progress.length > 0 ? (
            <div>
              <div className="panel-title" style={{ marginBottom: 8 }}>
                Enable Progress
              </div>
              <div className="wizard-steps">
                {progress.map((stage) => (
                  <div key={stage.name} className={`wizard-step ${stage.status}`}>
                    <div className="wizard-step-icon">
                      <StageIcon status={stage.status} />
                    </div>
                    <div>
                      <div className="wizard-step-title">{stage.name}</div>
                      {stage.message ? <div className="wizard-step-msg">{stage.message}</div> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="wizard-steps">
              {[
                'Check Saved Configuration',
                'Authenticate',
                'Validate Permissions',
                'Validate Endpoint',
                'Test Telemetry Access',
                'Discover Agents',
                'Register Agents',
                'Start Telemetry Collection',
              ].map((name) => (
                <div key={name} className="wizard-step">
                  <div className="wizard-step-icon">—</div>
                  <div className="wizard-step-title">{name}</div>
                </div>
              ))}
            </div>
          )}

          {message ? <div className="disabled-banner">{message}</div> : null}
        </div>
        <div className="side-panel-footer">
          <button type="button" className="btn" onClick={test} disabled={testing}>
            {testing ? 'Testing…' : 'Test Connection'}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </>
  );
}
