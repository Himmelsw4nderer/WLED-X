import { useCallback, useMemo, useRef } from "react";
import type { Dispatch, DragEvent, SetStateAction } from "react";
import {
  addEdge,
  Background,
  BackgroundVariant,
  ConnectionLineType,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "reactflow";
import type { Connection, Edge, Node, NodeTypes, OnEdgesChange, OnNodesChange } from "reactflow";
import "reactflow/dist/style.css";
import type { NodeTypeDescriptor } from "../../types";
import { EffectNode } from "./EffectNode";
import { createNodeId, defaultDataForDescriptor, edgeSocketType, isValidSocketConnection, makeEdgeId, PALETTE_MIME } from "./graphUtils";
import { SOCKET_COLORS } from "./socketColors";
import "./NodeCanvas.css";

interface NodeCanvasProps {
  nodes: Node<Record<string, unknown>>[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  setNodes: Dispatch<SetStateAction<Node<Record<string, unknown>>[]>>;
  setEdges: Dispatch<SetStateAction<Edge[]>>;
  descriptors: NodeTypeDescriptor[];
  descriptorsByType: Map<string, NodeTypeDescriptor>;
  onDirty: () => void;
}

// useReactFlow only works inside a ReactFlowProvider, so this outer component just
// supplies that provider and delegates everything else to NodeCanvasInner.
export function NodeCanvas(props: NodeCanvasProps) {
  return (
    <ReactFlowProvider>
      <NodeCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

function NodeCanvasInner({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  setNodes,
  setEdges,
  descriptors,
  descriptorsByType,
  onDirty,
}: NodeCanvasProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useReactFlow();

  // One EffectNode component registered under every node type string so reactflow
  // routes all of them through the same data-driven renderer.
  const nodeTypes = useMemo<NodeTypes>(() => {
    const map: NodeTypes = {};
    for (const descriptor of descriptors) map[descriptor.type] = EffectNode;
    return map;
  }, [descriptors]);

  // Cables are drawn in the colour of whatever socket type flows through them,
  // so a graph reads at a glance: gold = scalar, cyan = field, magenta = color.
  const styledEdges = useMemo<Edge[]>(
    () =>
      edges.map((edge) => {
        const socketType = edgeSocketType(edge, nodes, descriptorsByType);
        const stroke = socketType ? SOCKET_COLORS[socketType] : "var(--text-dim)";
        return {
          ...edge,
          type: edge.type ?? "smoothstep",
          className: `effect-edge${socketType ? ` effect-edge--${socketType}` : ""}`,
          style: { ...edge.style, stroke, strokeWidth: 2.5 },
        };
      }),
    [edges, nodes, descriptorsByType],
  );

  const handleNodesChange = useCallback<OnNodesChange>(
    (changes) => {
      onNodesChange(changes);
      if (changes.some((change) => change.type !== "select")) onDirty();
    },
    [onNodesChange, onDirty],
  );

  const handleEdgesChange = useCallback<OnEdgesChange>(
    (changes) => {
      onEdgesChange(changes);
      if (changes.some((change) => change.type !== "select")) onDirty();
    },
    [onEdgesChange, onDirty],
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, id: makeEdgeId(connection) }, eds));
      onDirty();
    },
    [setEdges, onDirty],
  );

  const handleIsValidConnection = useCallback(
    (edgeOrConnection: Edge | Connection) => isValidSocketConnection(edgeOrConnection, nodes, descriptorsByType),
    [nodes, descriptorsByType],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const type = event.dataTransfer.getData(PALETTE_MIME);
      const descriptor = descriptorsByType.get(type);
      if (!descriptor) return;

      const position = reactFlowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const newNode: Node<Record<string, unknown>> = {
        id: createNodeId(descriptor.type),
        type: descriptor.type,
        position,
        data: defaultDataForDescriptor(descriptor),
      };
      setNodes((nds) => [...nds, newNode]);
      onDirty();
    },
    [descriptorsByType, reactFlowInstance, setNodes, onDirty],
  );

  return (
    <div className="node-canvas" ref={wrapperRef} onDragOver={handleDragOver} onDrop={handleDrop}>
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        isValidConnection={handleIsValidConnection}
        nodeTypes={nodeTypes}
        deleteKeyCode={["Backspace", "Delete"]}
        connectionLineType={ConnectionLineType.SmoothStep}
        connectionLineStyle={{ stroke: "var(--gold)", strokeWidth: 2.5 }}
        proOptions={{ hideAttribution: true }}
        fitView
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.5} color="rgba(139, 92, 246, 0.28)" />
        <Controls />
        <MiniMap pannable zoomable nodeColor="#241b3d" nodeStrokeColor="#2a2140" maskColor="rgba(8, 6, 13, 0.7)" />
      </ReactFlow>
    </div>
  );
}
