import type { EffectGraph } from "../../types";

// The effect editor and its popped-out debug window (see DebugPopoutPage)
// aren't in the same React tree -- a real separate browser window, so it can
// live on a second monitor -- so the in-progress (possibly unsaved) graph has
// to cross over a BroadcastChannel instead of props/context. One channel per
// effect id keeps multiple editor tabs from crosstalking.
export function debugChannelName(effectId: number | string): string {
  return `wledx-debug-${effectId}`;
}

export type DebugChannelMessage =
  // Editor -> popout: the latest in-progress graph, sent on every change and
  // in reply to "hello" so a popout opened after edits already exist still
  // gets them immediately instead of waiting for the next edit.
  | { type: "graph"; graph: EffectGraph }
  // Popout -> editor: "I just opened/reloaded, send your current graph."
  | { type: "hello" };
