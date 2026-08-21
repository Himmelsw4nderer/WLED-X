import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useEdgesState, useNodesState } from "reactflow";
import type { Edge, Node } from "reactflow";
import { nodesApi } from "../api/resources";
import { DebugBar } from "../components/nodegraph/DebugBar";
import { ExposedParamsPanel } from "../components/nodegraph/ExposedParamsPanel";
import { NodeCanvas } from "../components/nodegraph/NodeCanvas";
import { NodeGraphContext } from "../components/nodegraph/NodeGraphContext";
import type { NodeGraphContextValue } from "../components/nodegraph/NodeGraphContext";
import { NodePalette } from "../components/nodegraph/NodePalette";
import { useDebugPreview } from "../components/nodegraph/useDebugPreview";
import { useEffectStore } from "../store/useEffectStore";
import type { EffectGraph, ExposedParam, NodeParam, NodeTypeDescriptor } from "../types";
import "./EffectEditorPage.css";

type FlowNode = Node<Record<string, unknown>>;

export function EffectEditorPage() {
  const { effectId } = useParams();
  const numericId = Number(effectId);
  const navigate = useNavigate();
  const { effects, loading, refresh, update } = useEffectStore();

  const [descriptors, setDescriptors] = useState<NodeTypeDescriptor[]>([]);
  const [descriptorsError, setDescriptorsError] = useState<string | null>(null);
  const [ready, setReady] = useState(() => useEffectStore.getState().effects.length > 0);
  const refreshedRef = useRef(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState<Record<string, unknown>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [exposedParams, setExposedParams] = useState<ExposedParam[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [debugOn, setDebugOn] = useState(false);
  const [debugLedCount, setDebugLedCount] = useState(24);

  const initializedForId = useRef<number | null>(null);
  const effect = effects.find((e) => e.id === numericId);

  useEffect(() => {
    nodesApi
      .list()
      .then(setDescriptors)
      .catch(() => setDescriptorsError("Could not load node types from the backend."));
  }, []);

  useEffect(() => {
    if (!refreshedRef.current && effects.length === 0) {
      refreshedRef.current = true;
      void refresh().finally(() => setReady(true));
    }
  }, [effects.length, refresh]);

  useEffect(() => {
    if (effect && initializedForId.current !== effect.id) {
      initializedForId.current = effect.id;
      setName(effect.name);
      setDescription(effect.description);
      setNodes(effect.graph.nodes as FlowNode[]);
      setEdges(effect.graph.edges as Edge[]);
      setExposedParams(effect.exposed_params);
      setDirty(false);
    }
  }, [effect, setNodes, setEdges]);

  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (dirty) e.preventDefault();
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  const descriptorsByType = useMemo(() => new Map(descriptors.map((d) => [d.type, d])), [descriptors]);

  const markDirty = useCallback(() => setDirty(true), []);

  const updateParam = useCallback(
    (nodeId: string, key: string, value: unknown) => {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, [key]: value } } : n)));
      markDirty();
    },
    [setNodes, markDirty],
  );

  const isExposed = useCallback(
    (nodeId: string, key: string) => exposedParams.some((p) => p.node_id === nodeId && p.param_key === key),
    [exposedParams],
  );

  const toggleExposed = useCallback(
    (nodeId: string, key: string, param: NodeParam, currentValue: unknown) => {
      setExposedParams((prev) => {
        const idx = prev.findIndex((p) => p.node_id === nodeId && p.param_key === key);
        if (idx >= 0) return prev.filter((_, i) => i !== idx);
        const numeric = typeof currentValue === "number" ? currentValue : typeof param.default === "number" ? param.default : 0;
        const min = typeof param.min === "number" ? param.min : 0;
        const max = typeof param.max === "number" ? param.max : 1;
        return [...prev, { node_id: nodeId, param_key: key, label: key, min, max, default: numeric }];
      });
      markDirty();
    },
    [markDirty],
  );

  const updateExposedParam = useCallback(
    (index: number, patch: Partial<ExposedParam>) => {
      setExposedParams((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)));
      markDirty();
    },
    [markDirty],
  );

  const removeExposedParam = useCallback(
    (index: number) => {
      setExposedParams((prev) => prev.filter((_, i) => i !== index));
      markDirty();
    },
    [markDirty],
  );

  const currentGraph = useMemo<EffectGraph>(
    () => ({
      nodes: nodes.map((n) => ({ id: n.id, type: n.type ?? "", position: n.position, data: n.data })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.sourceHandle ?? null,
        target: e.target,
        targetHandle: e.targetHandle ?? null,
      })),
    }),
    [nodes, edges],
  );

  const { result: debugResult, error: debugError } = useDebugPreview(debugOn, currentGraph, debugLedCount);

  const graphContextValue = useMemo<NodeGraphContextValue>(
    () => ({
      descriptorsByType,
      updateParam,
      isExposed,
      toggleExposed,
      nodePreview: debugResult?.nodes ?? null,
    }),
    [descriptorsByType, updateParam, isExposed, toggleExposed, debugResult],
  );

  async function handleSave() {
    if (!effect) return;
    setSaving(true);
    setSaveError(null);
    try {
      await update(effect.id, { name, description, graph: currentGraph, exposed_params: exposedParams });
      setDirty(false);
    } catch {
      setSaveError("Failed to save. Your edits are still here — try again.");
    } finally {
      setSaving(false);
    }
  }

  if (descriptorsError) {
    return (
      <div className="page effect-editor effect-editor--message">
        <div className="banner banner--error">{descriptorsError}</div>
      </div>
    );
  }

  if (!effect) {
    if (!ready || loading) {
      return <div className="page effect-editor effect-editor--message">Loading…</div>;
    }
    return (
      <div className="page effect-editor effect-editor--message">
        <p>Effect not found.</p>
        <button className="btn" onClick={() => navigate("/effects")}>
          Back to effects
        </button>
      </div>
    );
  }

  return (
    <div className="page effect-editor">
      <header className="effect-editor__header">
        <div className="effect-editor__title-row">
          <Link className="effect-editor__back" to="/effects">
            ← Effects
          </Link>
          <input
            className="effect-editor__name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              markDirty();
            }}
          />
          <div className="effect-editor__save-area">
            {saveError && <span className="effect-editor__save-error">{saveError}</span>}
            {dirty && !saveError && <span className="effect-editor__dirty">Unsaved changes</span>}
            <button className="btn btn--accent" onClick={() => void handleSave()} disabled={saving || !dirty}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
        <input
          className="effect-editor__description"
          placeholder="Description"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            markDirty();
          }}
        />
        <p className="effect-editor__hint">
          Toggle Debug below to see this graph running live against a synthetic strip — every node shows its
          current output. For the real thing, assign this effect to a fixture from the{" "}
          <Link to="/console">Console</Link> and watch it on the <Link to="/builder">3D Builder</Link> page.
        </p>
      </header>

      <DebugBar
        enabled={debugOn}
        onToggle={setDebugOn}
        ledCount={debugLedCount}
        onLedCountChange={setDebugLedCount}
        result={debugResult}
        error={debugError}
      />

      <div className="effect-editor__body">
        <NodeGraphContext.Provider value={graphContextValue}>
          <NodePalette descriptors={descriptors} />
          <NodeCanvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            setNodes={setNodes}
            setEdges={setEdges}
            descriptors={descriptors}
            descriptorsByType={descriptorsByType}
            onDirty={markDirty}
          />
          <ExposedParamsPanel params={exposedParams} onUpdate={updateExposedParam} onRemove={removeExposedParam} />
        </NodeGraphContext.Provider>
      </div>
    </div>
  );
}
