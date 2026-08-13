import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { MCPSummary, ToolSummary } from '../types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatRelative,
} from '../utils/format';

export function ToolsMcpPage() {
  const [tab, setTab] = useState<'Tools' | 'MCP'>('Tools');
  const [tools, setTools] = useState<ToolSummary[]>([]);
  const [mcp, setMcp] = useState<MCPSummary[]>([]);
  const [toolsEmpty, setToolsEmpty] = useState<{ title: string; message: string } | null>(null);
  const [mcpEmpty, setMcpEmpty] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [t, m] = await Promise.all([api.getTools(), api.getMcp()]);
      if (t.empty) {
        setToolsEmpty({ title: t.title ?? 'No tool telemetry', message: t.message ?? 'No live data' });
        setTools([]);
      } else {
        setToolsEmpty(null);
        setTools(t.items);
      }
      if (m.empty) {
        setMcpEmpty({ title: m.title ?? 'No MCP telemetry', message: m.message ?? 'No live data' });
        setMcp([]);
      } else {
        setMcpEmpty(null);
        setMcp(m.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tools/MCP');
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="stack">
      <div className="tabs">
        <button type="button" className={`tab${tab === 'Tools' ? ' active' : ''}`} onClick={() => setTab('Tools')}>
          Tools
        </button>
        <button type="button" className={`tab${tab === 'MCP' ? ' active' : ''}`} onClick={() => setTab('MCP')}>
          MCP
        </button>
      </div>

      {tab === 'Tools' ? (
        <div className="panel">
          {toolsEmpty ? (
            <EmptyState title={toolsEmpty.title} message={toolsEmpty.message} />
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Tool</th>
                    <th>Type</th>
                    <th>Agent</th>
                    <th>Calls</th>
                    <th>Success</th>
                    <th>Failure</th>
                    <th>Avg Latency</th>
                    <th>Retries</th>
                    <th>Last</th>
                    <th>Health</th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((t) => (
                    <tr key={`${t.name}-${t.agent_id}`}>
                      <td>{t.name}</td>
                      <td>{displayOrDash(t.tool_type)}</td>
                      <td>{displayOrDash(t.agent_name)}</td>
                      <td className="mono">{formatNumber(t.calls)}</td>
                      <td className="mono">{formatNumber(t.success)}</td>
                      <td className="mono">{formatNumber(t.failure)}</td>
                      <td className="mono">{formatDuration(t.average_latency_ms)}</td>
                      <td className="mono">{formatNumber(t.retries)}</td>
                      <td className="mono">{formatRelative(t.last_invocation)}</td>
                      <td>{displayOrDash(t.health)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="panel">
          {mcpEmpty ? (
            <EmptyState title={mcpEmpty.title} message={mcpEmpty.message} />
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Server</th>
                    <th>Tool</th>
                    <th>Agents</th>
                    <th>Calls</th>
                    <th>Success</th>
                    <th>Failure</th>
                    <th>Timeouts</th>
                    <th>Auth Errors</th>
                    <th>Avg Latency</th>
                    <th>Last</th>
                    <th>Health</th>
                  </tr>
                </thead>
                <tbody>
                  {mcp.map((m) => (
                    <tr key={`${m.server}-${m.tool}`}>
                      <td>{m.server}</td>
                      <td>{displayOrDash(m.tool)}</td>
                      <td className="mono">{formatNumber(m.connected_agents)}</td>
                      <td className="mono">{formatNumber(m.calls)}</td>
                      <td className="mono">{formatNumber(m.success)}</td>
                      <td className="mono">{formatNumber(m.failure)}</td>
                      <td className="mono">{formatNumber(m.timeouts)}</td>
                      <td className="mono">{formatNumber(m.auth_errors)}</td>
                      <td className="mono">{formatDuration(m.average_latency_ms)}</td>
                      <td className="mono">{formatRelative(m.last_invocation)}</td>
                      <td>{displayOrDash(m.health)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
