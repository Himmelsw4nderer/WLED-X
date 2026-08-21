import { create } from "zustand";
import { fixturesApi } from "../api/resources";
import type { Fixture, FixtureCreate, FixtureUpdate } from "../types";

interface FixtureStore {
  fixtures: Fixture[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (payload: FixtureCreate) => Promise<Fixture>;
  update: (id: number, payload: FixtureUpdate) => Promise<void>;
  remove: (id: number) => Promise<void>;
}

export const useFixtureStore = create<FixtureStore>((set, get) => ({
  fixtures: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    try {
      const fixtures = await fixturesApi.list();
      set({ fixtures });
    } finally {
      set({ loading: false });
    }
  },
  add: async (payload) => {
    const fixture = await fixturesApi.create(payload);
    set({ fixtures: [...get().fixtures, fixture] });
    return fixture;
  },
  update: async (id, payload) => {
    const updated = await fixturesApi.update(id, payload);
    set({ fixtures: get().fixtures.map((f) => (f.id === id ? updated : f)) });
  },
  remove: async (id) => {
    await fixturesApi.remove(id);
    set({ fixtures: get().fixtures.filter((f) => f.id !== id) });
  },
}));
