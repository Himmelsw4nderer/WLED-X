import { useEffect, useRef, useState } from "react";
import { effectsApi } from "../../api/resources";
import type { EffectGraph, RoomPreviewResponse } from "../../types";

// Same self-pacing poll as useDebugPreview, just against every real fixture
// instead of one synthetic strip -- see that file for why 40ms is fine.
const POLL_MS = 40;

/**
 * Polls /api/effects/preview_room while `enabled`, always sending the latest
 * in-editor graph -- the 3D room-view counterpart to useDebugPreview's 2D
 * strip. Used both inline in the effect editor and in the popped-out debug
 * window (see DebugPopoutPage), which keeps its own instance in sync with
 * whatever graph the editor last broadcast over a BroadcastChannel.
 */
export function useDebugRoomPreview(enabled: boolean, graph: EffectGraph) {
  const [result, setResult] = useState<RoomPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const graphRef = useRef(graph);
  useEffect(() => {
    graphRef.current = graph;
  }, [graph]);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const res = await effectsApi.previewRoom({ graph: graphRef.current });
        if (!cancelled) {
          setResult(res);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Room preview failed — check the graph for an invalid connection or cycle.");
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    }
    void tick();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [enabled]);

  return { result: enabled ? result : null, error: enabled ? error : null };
}
