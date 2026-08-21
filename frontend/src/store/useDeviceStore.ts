import { create } from "zustand";
import { devicesApi } from "../api/resources";
import type { Device, DeviceCreate } from "../types";

interface DeviceStore {
  devices: Device[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (payload: DeviceCreate) => Promise<Device>;
  remove: (id: number) => Promise<void>;
}

export const useDeviceStore = create<DeviceStore>((set, get) => ({
  devices: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    try {
      const devices = await devicesApi.list();
      set({ devices });
    } finally {
      set({ loading: false });
    }
  },
  add: async (payload) => {
    const device = await devicesApi.create(payload);
    set({ devices: [...get().devices, device] });
    return device;
  },
  remove: async (id) => {
    await devicesApi.remove(id);
    set({ devices: get().devices.filter((d) => d.id !== id) });
  },
}));
