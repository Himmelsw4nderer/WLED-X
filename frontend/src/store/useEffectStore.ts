import { create } from "zustand";
import { effectsApi } from "../api/resources";
import type { Effect, EffectCreate, EffectUpdate } from "../types";

interface EffectStore {
  effects: Effect[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (payload: EffectCreate) => Promise<Effect>;
  update: (id: number, payload: EffectUpdate) => Promise<Effect>;
  remove: (id: number) => Promise<void>;
}

export const useEffectStore = create<EffectStore>((set, get) => ({
  effects: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    try {
      const effects = await effectsApi.list();
      set({ effects });
    } finally {
      set({ loading: false });
    }
  },
  add: async (payload) => {
    const effect = await effectsApi.create(payload);
    set({ effects: [...get().effects, effect] });
    return effect;
  },
  update: async (id, payload) => {
    const updated = await effectsApi.update(id, payload);
    set({ effects: get().effects.map((e) => (e.id === id ? updated : e)) });
    return updated;
  },
  remove: async (id) => {
    await effectsApi.remove(id);
    set({ effects: get().effects.filter((e) => e.id !== id) });
  },
}));
