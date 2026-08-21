import { create } from "zustand";
import { liveSocket } from "../api/ws";
import type { ConsoleState } from "../types";

// Wire contract with the backend console module (lumen/console + api/ws.py):
//   server -> client: {"type": "console_state", ...ConsoleState}
//   client -> server: {"type": "console_set", ...Partial<ConsoleState>}
//   client -> server: {"type": "console_hit"}  -- pulses `hype` to 1.0, decays server-side

interface ConsoleStore extends ConsoleState {
  connect: () => void;
  setMasterBrightness: (value: number) => void;
  setParamOverride: (key: string, value: number) => void;
  setActiveScene: (sceneId: number | null) => void;
  hit: () => void;
}

let connected = false;

export const useConsoleStore = create<ConsoleStore>((set, get) => ({
  master_brightness: 1,
  active_scene_id: null,
  param_overrides: {},
  hype: 0,

  connect: () => {
    if (connected) return;
    connected = true;
    liveSocket.connect();
    liveSocket.on("console_state", (message) => {
      const { type: _type, ...state } = message;
      set(state as Partial<ConsoleState>);
    });
  },

  setMasterBrightness: (value) => {
    set({ master_brightness: value });
    liveSocket.send({ type: "console_set", master_brightness: value });
  },

  setParamOverride: (key, value) => {
    const param_overrides = { ...get().param_overrides, [key]: value };
    set({ param_overrides });
    liveSocket.send({ type: "console_set", param_overrides });
  },

  setActiveScene: (sceneId) => {
    set({ active_scene_id: sceneId });
    liveSocket.send({ type: "console_set", active_scene_id: sceneId });
  },

  hit: () => {
    liveSocket.send({ type: "console_hit" });
  },
}));
