import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { SceneViewer } from "../components/3d/SceneViewer";
import { debugChannelName } from "../components/nodegraph/debugChannel";
import type { DebugChannelMessage } from "../components/nodegraph/debugChannel";
import { useDebugRoomPreview } from "../components/nodegraph/useDebugRoomPreview";
import { useEffectStore } from "../store/useEffectStore";
import { useFixtureStore } from "../store/useFixtureStore";
import type { EffectGraph } from "../types";
import "./DebugPopoutPage.css";

const EMPTY_GRAPH: EffectGraph = { nodes: [], edges: [] };

/** A standalone window (no app chrome) that mirrors the effect editor's 3D
 * room view -- opened via window.open from EffectEditorPage so it can be
 * dragged onto a second monitor while you keep working in the main window.
 * It never talks to the backend for the graph itself; the editor broadcasts
 * its in-progress (possibly unsaved) graph over a BroadcastChannel, and this
 * page just polls /preview_room with whatever it last received. */
export function DebugPopoutPage() {
  const { effectId } = useParams();
  const effects = useEffectStore((s) => s.effects);
  const refreshEffects = useEffectStore((s) => s.refresh);
  const fixtures = useFixtureStore((s) => s.fixtures);
  const refreshFixtures = useFixtureStore((s) => s.refresh);
  const [graph, setGraph] = useState<EffectGraph | null>(null);

  useEffect(() => {
    void refreshFixtures();
    void refreshEffects();
  }, [refreshFixtures, refreshEffects]);

  useEffect(() => {
    if (!effectId) return;
    const channel = new BroadcastChannel(debugChannelName(effectId));
    channel.onmessage = (event: MessageEvent<DebugChannelMessage>) => {
      if (event.data.type === "graph") setGraph(event.data.graph);
    };
    channel.postMessage({ type: "hello" } satisfies DebugChannelMessage);
    return () => channel.close();
  }, [effectId]);

  const { result, error } = useDebugRoomPreview(graph !== null, graph ?? EMPTY_GRAPH);
  const effect = effects.find((e) => String(e.id) === effectId);

  return (
    <div className="debug-popout">
      <div className="debug-popout__hud">
        <span className="debug-popout__title">Live preview</span>
        <span>{effect ? effect.name : `Effect #${effectId}`}</span>
        {!graph && <span className="debug-popout__hint">Waiting for the effect editor…</span>}
        {error && <span className="debug-popout__error">{error}</span>}
      </div>
      <SceneViewer fixtures={fixtures} selectedId={null} onSelect={() => {}} colorsOverride={result?.fixtures ?? {}} />
    </div>
  );
}
