// Small framework-free helpers shared by NodeCanvas/EffectNode. No graph evaluation logic
// lives here — only the bits needed to build/edit/persist the graph shape.

import type { Connection, Edge, Node } from "reactflow";
import type { NodeSocketType, NodeTypeDescriptor } from "../../types";

export const PALETTE_MIME = "application/x-wled-x-node-type";

let nodeIdCounter = 0;

export function createNodeId(type: string): string {
  nodeIdCounter += 1;
  const suffix =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().slice(0, 8)
      : `${Date.now().toString(36)}${nodeIdCounter}`;
  return `${type}-${suffix}`;
}

export function makeEdgeId(connection: Connection): string {
  const random = Math.random().toString(36).slice(2, 8);
  return `e-${connection.source ?? "?"}-${connection.sourceHandle ?? "out"}-${connection.target ?? "?"}-${connection.targetHandle ?? "in"}-${random}`;
}

export function defaultDataForDescriptor(descriptor: NodeTypeDescriptor): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const param of descriptor.params) {
    data[param.key] = cloneParamDefault(param.default);
  }
  return data;
}

function cloneParamDefault(value: unknown): unknown {
  if (value === null || typeof value !== "object") return value;
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as unknown;
}

function getSocketType(
  nodes: Node[],
  descriptorsByType: Map<string, NodeTypeDescriptor>,
  nodeId: string | null | undefined,
  handleId: string | null | undefined,
  direction: "input" | "output",
): NodeSocketType | undefined {
  if (!nodeId) return undefined;
  const node = nodes.find((n) => n.id === nodeId);
  if (!node?.type) return undefined;
  const descriptor = descriptorsByType.get(node.type);
  if (!descriptor) return undefined;
  const sockets = direction === "input" ? descriptor.inputs : descriptor.outputs;
  const socket = handleId ? sockets.find((s) => s.key === handleId) : sockets[0];
  return socket?.type;
}

// The output socket type a given edge carries -- used to colour the cable by
// what flows through it (scalar=gold, field=cyan, color=magenta).
export function edgeSocketType(
  edge: Pick<Edge, "source" | "sourceHandle">,
  nodes: Node[],
  descriptorsByType: Map<string, NodeTypeDescriptor>,
): NodeSocketType | undefined {
  return getSocketType(nodes, descriptorsByType, edge.source, edge.sourceHandle, "output");
}

// Deliberately permissive: scalars broadcast into fields on the backend, so any
// scalar <-> field link is allowed. The two (N,3)-shaped types -- color and
// vec3 -- are structural, not interchangeable: each only connects to its own
// kind, never to a scalar/field or to each other.
const STRUCTURAL_SOCKETS: readonly NodeSocketType[] = ["color", "vec3"];

export function isValidSocketConnection(
  edgeOrConnection: Edge | Connection,
  nodes: Node[],
  descriptorsByType: Map<string, NodeTypeDescriptor>,
): boolean {
  const sourceType = getSocketType(nodes, descriptorsByType, edgeOrConnection.source, edgeOrConnection.sourceHandle, "output");
  const targetType = getSocketType(nodes, descriptorsByType, edgeOrConnection.target, edgeOrConnection.targetHandle, "input");
  if (!sourceType || !targetType) return true;
  if (sourceType === targetType) return true;
  return !STRUCTURAL_SOCKETS.includes(sourceType) && !STRUCTURAL_SOCKETS.includes(targetType);
}
