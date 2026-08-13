import { useEffect, useMemo } from 'react';
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { WorkflowGraph as WFGraph } from '../types';
import { EmptyState } from './EmptyState';
import { WorkflowNode, type WorkflowFlowNode, type WorkflowNodeData } from './WorkflowNode';

const nodeTypes = { workflow: WorkflowNode };

const NODE_WIDTH = 220;
const COL_GAP = 280;
const ROW_GAP = 150;

function layoutNodes(graph: WFGraph): WorkflowFlowNode[] {
  const levels = new Map<string, number>();
  const children = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  const uniqueNodes = new Map(graph.nodes.map((n) => [n.id, n]));

  for (const id of uniqueNodes.keys()) {
    indeg.set(id, 0);
    children.set(id, []);
  }
  for (const e of graph.edges) {
    if (!uniqueNodes.has(e.source) || !uniqueNodes.has(e.target)) continue;
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
    const kids = children.get(e.source) ?? [];
    if (!kids.includes(e.target)) kids.push(e.target);
    children.set(e.source, kids);
  }

  const roots = [...uniqueNodes.keys()].filter((id) => (indeg.get(id) ?? 0) === 0);
  const queue = roots.length ? [...roots] : [...uniqueNodes.keys()].slice(0, 1);
  queue.forEach((id) => levels.set(id, 0));
  const seen = new Set(queue);
  while (queue.length) {
    const id = queue.shift()!;
    const lvl = levels.get(id) ?? 0;
    for (const child of children.get(id) ?? []) {
      const next = Math.max(levels.get(child) ?? 0, lvl + 1);
      levels.set(child, next);
      if (!seen.has(child)) {
        seen.add(child);
        queue.push(child);
      }
    }
  }

  // Orphans / unresolved nodes with no path from a root stay at level 0 unless edged.
  for (const id of uniqueNodes.keys()) {
    if (!levels.has(id)) levels.set(id, 0);
  }

  const byLevel = new Map<number, string[]>();
  for (const id of uniqueNodes.keys()) {
    const lvl = levels.get(id) ?? 0;
    const list = byLevel.get(lvl) ?? [];
    list.push(id);
    byLevel.set(lvl, list);
  }

  // Stable order within a level by original node order / name
  const orderIndex = new Map([...uniqueNodes.keys()].map((id, i) => [id, i]));
  for (const [lvl, ids] of byLevel) {
    ids.sort((a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0));
    byLevel.set(lvl, ids);
  }

  return [...uniqueNodes.values()].map((n) => {
    const lvl = levels.get(n.id) ?? 0;
    const siblings = byLevel.get(lvl) ?? [n.id];
    const idx = siblings.indexOf(n.id);
    const data: WorkflowNodeData = { ...n };
    return {
      id: n.id,
      type: 'workflow' as const,
      position: { x: lvl * COL_GAP, y: idx * ROW_GAP },
      data,
      style: { width: NODE_WIDTH },
      sourcePosition: undefined,
      targetPosition: undefined,
    };
  });
}

function toEdges(graph: WFGraph): Edge[] {
  const nodeIds = new Set(graph.nodes.map((n) => n.id));
  const seen = new Set<string>();
  const edges: Edge[] = [];
  for (const e of graph.edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue;
    const id = e.id || `${e.source}->${e.target}`;
    if (seen.has(id)) continue;
    seen.add(id);
    edges.push({
      id,
      source: e.source,
      target: e.target,
      label: e.label ?? e.edge_type?.replace(/_/g, ' ') ?? '',
      animated: graph.status === 'running',
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#6b7c90' },
      style: { stroke: '#6b7c90', strokeWidth: 1.5 },
      labelStyle: { fill: '#9aabbf', fontSize: 10, fontFamily: 'IBM Plex Sans' },
      labelBgStyle: { fill: '#111821', fillOpacity: 0.92 },
      labelBgPadding: [4, 6] as [number, number],
    });
  }
  return edges;
}

function FitViewOnGraphChange({ graphKey }: { graphKey: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = window.setTimeout(() => {
      void fitView({ padding: 0.22, duration: 200, minZoom: 0.25, maxZoom: 1.25 });
    }, 40);
    return () => window.clearTimeout(id);
  }, [graphKey, fitView]);
  return null;
}

interface WorkflowGraphProps {
  graph: WFGraph | null;
  highlightRunning?: boolean;
  height?: number | string;
  emptyTitle?: string;
  emptyMessage?: string;
}

function WorkflowGraphInner({
  graph,
  height = 420,
}: {
  graph: WFGraph;
  height: number | string;
}) {
  const initialNodes = useMemo(() => layoutNodes(graph), [graph]);
  const initialEdges = useMemo(() => toEdges(graph), [graph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const graphKey = `${graph.execution_id}:${graph.nodes.length}:${graph.edges.length}`;

  useEffect(() => {
    setNodes(layoutNodes(graph));
    setEdges(toEdges(graph));
  }, [graph, setNodes, setEdges]);

  return (
    <div className="workflow-canvas" style={{ height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.22, minZoom: 0.25, maxZoom: 1.25 }}
        minZoom={0.2}
        maxZoom={1.5}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <FitViewOnGraphChange graphKey={graphKey} />
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
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  );
}

export function WorkflowGraph({
  graph,
  height = 420,
  emptyTitle = 'No executions received',
  emptyMessage = 'Select a live execution or wait for telemetry spans to build the workflow graph.',
}: WorkflowGraphProps) {
  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="workflow-canvas" style={{ height, display: 'flex' }}>
        <EmptyState title={emptyTitle} message={emptyMessage} compact />
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <WorkflowGraphInner graph={graph} height={height} />
    </ReactFlowProvider>
  );
}
