import { useEffect, useMemo } from 'react';
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { WorkflowGraph as WFGraph } from '../types';
import { EmptyState } from './EmptyState';
import { WorkflowNode, type WorkflowFlowNode, type WorkflowNodeData } from './WorkflowNode';

const nodeTypes = { workflow: WorkflowNode };

function layoutNodes(graph: WFGraph): WorkflowFlowNode[] {
  const levels = new Map<string, number>();
  const children = new Map<string, string[]>();
  const indeg = new Map<string, number>();

  for (const n of graph.nodes) {
    indeg.set(n.id, 0);
    children.set(n.id, []);
  }
  for (const e of graph.edges) {
    if (!indeg.has(e.target)) continue;
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
    children.get(e.source)?.push(e.target);
  }

  const queue = graph.nodes.filter((n) => (indeg.get(n.id) ?? 0) === 0).map((n) => n.id);
  queue.forEach((id) => levels.set(id, 0));
  while (queue.length) {
    const id = queue.shift()!;
    const lvl = levels.get(id) ?? 0;
    for (const child of children.get(id) ?? []) {
      const next = Math.max(levels.get(child) ?? 0, lvl + 1);
      levels.set(child, next);
      indeg.set(child, (indeg.get(child) ?? 1) - 1);
      if ((indeg.get(child) ?? 0) <= 0) queue.push(child);
    }
  }

  const byLevel = new Map<number, string[]>();
  for (const n of graph.nodes) {
    const lvl = levels.get(n.id) ?? 0;
    const list = byLevel.get(lvl) ?? [];
    list.push(n.id);
    byLevel.set(lvl, list);
  }

  return graph.nodes.map((n) => {
    const lvl = levels.get(n.id) ?? 0;
    const siblings = byLevel.get(lvl) ?? [n.id];
    const idx = siblings.indexOf(n.id);
    const data: WorkflowNodeData = { ...n };
    return {
      id: n.id,
      type: 'workflow' as const,
      position: { x: lvl * 260, y: idx * 140 },
      data,
    };
  });
}

function toEdges(graph: WFGraph): Edge[] {
  return graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label ?? e.edge_type?.replace(/_/g, ' ') ?? '',
    animated: graph.status === 'running',
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#6b7c90' },
    style: { stroke: '#6b7c90', strokeWidth: 1.4 },
    labelStyle: { fill: '#9aabbf', fontSize: 10, fontFamily: 'IBM Plex Sans' },
    labelBgStyle: { fill: '#111821', fillOpacity: 0.9 },
  }));
}

interface WorkflowGraphProps {
  graph: WFGraph | null;
  highlightRunning?: boolean;
  height?: number | string;
  emptyTitle?: string;
  emptyMessage?: string;
}

export function WorkflowGraph({
  graph,
  height = 420,
  emptyTitle = 'No executions received',
  emptyMessage = 'Select a live execution or wait for telemetry spans to build the workflow graph.',
}: WorkflowGraphProps) {
  const initialNodes = useMemo(() => (graph ? layoutNodes(graph) : []), [graph]);
  const initialEdges = useMemo(() => (graph ? toEdges(graph) : []), [graph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="workflow-canvas" style={{ height, display: 'flex' }}>
        <EmptyState title={emptyTitle} message={emptyMessage} compact />
      </div>
    );
  }

  return (
    <div className="workflow-canvas" style={{ height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.3}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={18} size={1} color="rgba(255,255,255,0.04)" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const s = (n.data as { status?: string; is_live?: boolean })?.status;
            if (s === 'running' || (n.data as { is_live?: boolean })?.is_live) return '#4a9eff';
            if (s === 'success') return '#3ecf8e';
            if (s === 'failed') return '#e85d5d';
            if (s === 'warning') return '#e8a838';
            return '#7a8a9e';
          }}
          maskColor="rgba(11,15,20,0.7)"
          style={{ background: '#0e141c' }}
        />
      </ReactFlow>
    </div>
  );
}
