import { useEffect, useRef, useState } from "react";
import { effectsApi } from "../../api/resources";
import type { EffectGraph, PreviewResponse } from "../../types";

const POLL_MS = 150;

/**
 * Polls the backend's /api/effects/preview endpoint while `enabled`, always
 * sending the latest in-editor graph (via a ref, so edits don't need to
 * restart the polling loop). The backend is the only place this graph is
 * ever actually evaluated -- there's no client-side evaluator to keep in
 * sync with it.
 */
export function useDebugPreview(enabled: boolean, graph: EffectGraph, ledCount: number) {
  const [result, setResult] = useState<PreviewResponse | null>(null);
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
        const res = await effectsApi.preview({ graph: graphRef.current, led_count: ledCount });
        if (!cancelled) {
          setResult(res);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Preview failed — check the graph for an invalid connection or cycle.");
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    }
    void tick();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [enabled, ledCount]);

  // Stale results from before the user turned debug off are masked here rather than
  // cleared via setState in the effect above, so turning it back on doesn't need to
  // wait a poll interval to show something.
  return { result: enabled ? result : null, error: enabled ? error : null };
}
