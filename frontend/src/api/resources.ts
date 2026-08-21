import { api } from "./client";
import type {
  Device,
  DeviceCreate,
  Effect,
  EffectCreate,
  EffectUpdate,
  Fixture,
  FixtureCreate,
  FixtureUpdate,
  Scene,
  SceneCreate,
  SceneUpdate,
} from "../types";

export const devicesApi = {
  list: () => api.get<Device[]>("/api/devices"),
  create: (payload: DeviceCreate) => api.post<Device>("/api/devices", payload),
  update: (id: number, payload: Partial<DeviceCreate>) =>
    api.patch<Device>(`/api/devices/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/api/devices/${id}`),
};

export const fixturesApi = {
  list: () => api.get<Fixture[]>("/api/fixtures"),
  create: (payload: FixtureCreate) => api.post<Fixture>("/api/fixtures", payload),
  update: (id: number, payload: FixtureUpdate) => api.patch<Fixture>(`/api/fixtures/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/api/fixtures/${id}`),
};

export const effectsApi = {
  list: () => api.get<Effect[]>("/api/effects"),
  create: (payload: EffectCreate) => api.post<Effect>("/api/effects", payload),
  update: (id: number, payload: EffectUpdate) => api.patch<Effect>(`/api/effects/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/api/effects/${id}`),
};

export const scenesApi = {
  list: () => api.get<Scene[]>("/api/scenes"),
  create: (payload: SceneCreate) => api.post<Scene>("/api/scenes", payload),
  update: (id: number, payload: SceneUpdate) => api.patch<Scene>(`/api/scenes/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/api/scenes/${id}`),
};
