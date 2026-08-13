import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { WorkflowNode as WFNode } from '../types';
import { formatDuration, formatNumber, statusTone } from '../utils/format';

export type WorkflowNodeData = WFNode & Record<string, unknown>;

export type WorkflowFlowNode = Node<WorkflowNodeData, 'workflow'>;

export function WorkflowNode({ data }: NodeProps<WorkflowFlowNode>) {
  const tone = statusTone(data.status ?? (data.is_live ? 'running' : 'unknown'));
  return (
    <div className={`workflow-node ${tone}`}>
      <Handle type="target" position={Position.Left} style={{ background: 'var(--border-strong)' }} />
      <div className="workflow-node-name">{data.name}</div>
      <div className="workflow-node-type">{data.node_type}</div>
      <div className="workflow-node-meta">
        <span>Status</span>
        <span>{data.status ?? (data.is_live ? 'running' : '—')}</span>
        <span>Duration</span>
        <span>{formatDuration(data.duration_ms)}</span>
        <span>Tokens</span>
        <span>{formatNumber(data.tokens)}</span>
        <span>Calls</span>
        <span>{formatNumber(data.call_count)}</span>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: 'var(--border-strong)' }} />
    </div>
  );
}
