/** Formatting helpers — never coerce null/undefined to zero. */

export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`;
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = ((ms % 60_000) / 1000).toFixed(0);
  return `${mins}m ${secs}s`;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '—';
  }
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso).getTime();
    const diff = Date.now() - d;
    if (diff < 0) return 'just now';
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return formatTimestamp(iso);
  } catch {
    return '—';
  }
}

export function displayOrDash(value: string | number | null | undefined): string {
  if (value == null || value === '') return '—';
  return String(value);
}

export function statusTone(
  status: string | null | undefined,
): 'success' | 'failed' | 'running' | 'warning' | 'unknown' {
  const s = (status ?? '').toLowerCase();
  if (['success', 'healthy', 'connected', 'telemetry_active', 'complete'].includes(s)) return 'success';
  if (['failed', 'critical', 'connection_failed', 'timeout', 'cancelled'].includes(s)) return 'failed';
  if (['running', 'live'].includes(s)) return 'running';
  if (['warning', 'partial', 'delayed', 'paused'].includes(s)) return 'warning';
  return 'unknown';
}

export function categoryLabel(key: string): string {
  const map: Record<string, string> = {
    cloud_platforms: 'Cloud Platforms',
    agent_platforms: 'Agent Platforms',
    observability: 'Observability',
    enterprise_tools: 'Enterprise Tools',
    protocols: 'Protocols',
    rag_data_sources: 'RAG / Data Sources',
  };
  return map[key] ?? key.replace(/_/g, ' ');
}
