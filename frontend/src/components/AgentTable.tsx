import { Link } from 'react-router-dom';
import type { AgentMeteringRow } from '../types';
import {
  displayOrDash,
  formatDuration,
  formatNumber,
  formatPercent,
  formatRelative,
} from '../utils/format';
import { AgentHealthBadge } from './AgentHealthBadge';
import { EmptyState } from './EmptyState';

interface AgentTableProps {
  rows: AgentMeteringRow[];
  emptyTitle?: string;
  emptyMessage?: string;
}

export function AgentTable({
  rows,
  emptyTitle = 'No agents discovered',
  emptyMessage = 'Connect and enable a platform to start receiving agent telemetry.',
}: AgentTableProps) {
  if (!rows.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} compact />;
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Cloud</th>
            <th>Platform</th>
            <th>Framework</th>
            <th>Model</th>
            <th>Executions</th>
            <th>Tokens</th>
            <th>Avg Steps</th>
            <th>Model Calls</th>
            <th>Tools</th>
            <th>MCP</th>
            <th>RAG</th>
            <th>A2A</th>
            <th>Avg Latency</th>
            <th>Success</th>
            <th>Health</th>
            <th>Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.agent_id}>
              <td>
                <Link className="row-link" to={`/agents/${row.agent_id}`}>
                  {row.agent_name}
                </Link>
              </td>
              <td>{displayOrDash(row.cloud)}</td>
              <td>{displayOrDash(row.platform)}</td>
              <td>{displayOrDash(row.framework)}</td>
              <td className="mono">{displayOrDash(row.model)}</td>
              <td className="mono">{formatNumber(row.executions)}</td>
              <td className="mono">{formatNumber(row.tokens)}</td>
              <td className="mono">{formatNumber(row.average_steps)}</td>
              <td className="mono">{formatNumber(row.model_calls)}</td>
              <td className="mono">{formatNumber(row.tool_calls)}</td>
              <td className="mono">{formatNumber(row.mcp_calls)}</td>
              <td className="mono">{formatNumber(row.rag_calls)}</td>
              <td className="mono">{formatNumber(row.a2a_calls)}</td>
              <td className="mono">{formatDuration(row.average_latency_ms)}</td>
              <td className="mono">{formatPercent(row.success_rate)}</td>
              <td>
                <AgentHealthBadge health={row.health} />
              </td>
              <td className="mono">{formatRelative(row.last_seen)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
