import { create } from "zustand";
import { colorSchemesApi } from "../api/resources";
import type { ColorScheme, ColorSchemeCreate, ColorSchemeUpdate } from "../types";

interface ColorSchemeStore {
  schemes: ColorScheme[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (payload: ColorSchemeCreate) => Promise<ColorScheme>;
  update: (id: number, payload: ColorSchemeUpdate) => Promise<ColorScheme>;
  remove: (id: number) => Promise<void>;
}

export const useColorSchemeStore = create<ColorSchemeStore>((set, get) => ({
  schemes: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    try {
      const schemes = await colorSchemesApi.list();
      set({ schemes });
    } finally {
      set({ loading: false });
    }
  },
  add: async (payload) => {
    const scheme = await colorSchemesApi.create(payload);
    set({ schemes: [...get().schemes, scheme] });
    return scheme;
  },
  update: async (id, payload) => {
    const updated = await colorSchemesApi.update(id, payload);
    set({ schemes: get().schemes.map((s) => (s.id === id ? updated : s)) });
    return updated;
  },
  remove: async (id) => {
    await colorSchemesApi.remove(id);
    set({ schemes: get().schemes.filter((s) => s.id !== id) });
  },
}));
