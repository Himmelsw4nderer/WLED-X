import { api } from "./client";
import type {
  AudioDeviceOption,
  AudioSource,
  AudioSourceUpdate,
  Device,
  DeviceCreate,
  Effect,
  EffectCreate,
  EffectUpdate,
  Fixture,
  FixtureCreate,
  FixtureUpdate,
  NodeTypeDescriptor,
  PreviewRequest,
  PreviewResponse,
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

// A WLED device found by discovery but not yet added to the project (no id).
export interface DiscoveredDevice {
  name: string;
  ip: string;
  mac?: string | null;
  led_count: number;
}

export const deviceDiscoveryApi = {
  mdns: () => api.get<DiscoveredDevice[]>("/api/devices/discover/mdns"),
  scan: () => api.post<DiscoveredDevice[]>("/api/devices/discover/scan"),
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
  duplicate: (id: number) => api.post<Effect>(`/api/effects/${id}/duplicate`),
  remove: (id: number) => api.delete<void>(`/api/effects/${id}`),
  preview: (payload: PreviewRequest) => api.post<PreviewResponse>("/api/effects/preview", payload),
};

export const scenesApi = {
  list: () => api.get<Scene[]>("/api/scenes"),
  create: (payload: SceneCreate) => api.post<Scene>("/api/scenes", payload),
  update: (id: number, payload: SceneUpdate) => api.patch<Scene>(`/api/scenes/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/api/scenes/${id}`),
};

export const nodesApi = {
  list: () => api.get<NodeTypeDescriptor[]>("/api/nodes"),
};

export const audioApi = {
  devices: () => api.get<AudioDeviceOption[]>("/api/audio/devices"),
  sources: () => api.get<AudioSource[]>("/api/audio/sources"),
  updateSource: (name: string, payload: AudioSourceUpdate) =>
    api.put<AudioSource>(`/api/audio/sources/${name}`, payload),
};
