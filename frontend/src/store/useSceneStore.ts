import { create } from "zustand";
import { scenesApi } from "../api/resources";
import type { Scene, SceneCreate, SceneUpdate } from "../types";

interface SceneStore {
  scenes: Scene[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (payload: SceneCreate) => Promise<Scene>;
  update: (id: number, payload: SceneUpdate) => Promise<Scene>;
  remove: (id: number) => Promise<void>;
  activate: (id: number) => Promise<void>;
}

export const useSceneStore = create<SceneStore>((set, get) => ({
  scenes: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    try {
      const scenes = await scenesApi.list();
      set({ scenes });
    } finally {
      set({ loading: false });
    }
  },
  add: async (payload) => {
    const scene = await scenesApi.create(payload);
    set({ scenes: [...get().scenes, scene] });
    return scene;
  },
  update: async (id, payload) => {
    const updated = await scenesApi.update(id, payload);
    set({ scenes: get().scenes.map((s) => (s.id === id ? updated : s)) });
    return updated;
  },
  remove: async (id) => {
    await scenesApi.remove(id);
    set({ scenes: get().scenes.filter((s) => s.id !== id) });
  },
  // Backend enforces only one active scene at a time (see routes_scenes.update_scene);
  // refresh afterward rather than optimistically flipping every row's `active` locally.
  activate: async (id) => {
    await scenesApi.update(id, { active: true });
    await get().refresh();
  },
}));
