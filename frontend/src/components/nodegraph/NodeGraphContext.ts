import { createContext, useContext } from "react";
import type { NodeParam, NodePreviewValue, NodeTypeDescriptor } from "../../types";

export interface NodeGraphContextValue {
  descriptorsByType: Map<string, NodeTypeDescriptor>;
  updateParam: (nodeId: string, key: string, value: unknown) => void;
  isExposed: (nodeId: string, key: string) => boolean;
  toggleExposed: (nodeId: string, key: string, param: NodeParam, currentValue: unknown) => void;
  /** Live per-node debug values from the preview endpoint, keyed by node id. Null when debug mode is off. */
  nodePreview: Record<string, NodePreviewValue> | null;
}

export const NodeGraphContext = createContext<NodeGraphContextValue | null>(null);

export function useNodeGraphContext(): NodeGraphContextValue {
  const ctx = useContext(NodeGraphContext);
  if (!ctx) {
    throw new Error("useNodeGraphContext must be used within a NodeGraphContext provider");
  }
  return ctx;
}
