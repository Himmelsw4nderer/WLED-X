import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/ws", () => {
  const listeners = new Map<string, Set<(msg: Record<string, unknown>) => void>>();
  return {
    liveSocket: {
      connect: vi.fn(),
      send: vi.fn(),
      on: vi.fn((type: string, cb: (msg: Record<string, unknown>) => void) => {
        if (!listeners.has(type)) listeners.set(type, new Set());
        listeners.get(type)!.add(cb);
        return () => listeners.get(type)?.delete(cb);
      }),
      __emit: (type: string, msg: Record<string, unknown>) => {
        listeners.get(type)?.forEach((cb) => cb(msg));
      },
    },
  };
});

async function freshStore() {
  const wsModule = await import("../api/ws");
  const storeModule = await import("./useConsoleStore");
  return {
    liveSocket: wsModule.liveSocket as unknown as {
      connect: ReturnType<typeof vi.fn>;
      send: ReturnType<typeof vi.fn>;
      on: ReturnType<typeof vi.fn>;
      __emit: (type: string, msg: Record<string, unknown>) => void;
    },
    useConsoleStore: storeModule.useConsoleStore,
  };
}

beforeEach(() => {
  vi.resetModules();
});

describe("useConsoleStore", () => {
  it("starts with the documented defaults", async () => {
    const { useConsoleStore } = await freshStore();
    const state = useConsoleStore.getState();
    expect(state.master_brightness).toBe(1);
    expect(state.active_scene_id).toBeNull();
    expect(state.param_overrides).toEqual({});
    expect(state.hype).toBe(0);
  });

  it("setMasterBrightness updates local state and sends a console_set message", async () => {
    const { useConsoleStore, liveSocket } = await freshStore();
    useConsoleStore.getState().setMasterBrightness(0.4);
    expect(useConsoleStore.getState().master_brightness).toBe(0.4);
    expect(liveSocket.send).toHaveBeenCalledWith({ type: "console_set", master_brightness: 0.4 });
  });

  it("setParamOverride merges into existing overrides rather than replacing them", async () => {
    const { useConsoleStore, liveSocket } = await freshStore();
    useConsoleStore.getState().setParamOverride("1:speed", 2);
    useConsoleStore.getState().setParamOverride("1:hue", 0.5);

    expect(useConsoleStore.getState().param_overrides).toEqual({ "1:speed": 2, "1:hue": 0.5 });
    expect(liveSocket.send).toHaveBeenLastCalledWith({
      type: "console_set",
      param_overrides: { "1:speed": 2, "1:hue": 0.5 },
    });
  });

  it("setActiveScene updates local state and sends a console_set message", async () => {
    const { useConsoleStore, liveSocket } = await freshStore();
    useConsoleStore.getState().setActiveScene(7);
    expect(useConsoleStore.getState().active_scene_id).toBe(7);
    expect(liveSocket.send).toHaveBeenCalledWith({ type: "console_set", active_scene_id: 7 });
  });

  it("hit sends a console_hit message without touching local state directly", async () => {
    const { useConsoleStore, liveSocket } = await freshStore();
    useConsoleStore.getState().hit();
    expect(liveSocket.send).toHaveBeenCalledWith({ type: "console_hit" });
    expect(useConsoleStore.getState().hype).toBe(0);
  });

  it("connect subscribes once and applies incoming console_state broadcasts", async () => {
    const { useConsoleStore, liveSocket } = await freshStore();
    useConsoleStore.getState().connect();
    useConsoleStore.getState().connect();

    expect(liveSocket.connect).toHaveBeenCalledTimes(1);
    expect(liveSocket.on).toHaveBeenCalledTimes(1);

    liveSocket.__emit("console_state", {
      type: "console_state",
      master_brightness: 0.6,
      active_scene_id: 3,
      param_overrides: { "2:x": 1 },
      hype: 0.9,
    });

    const state = useConsoleStore.getState();
    expect(state.master_brightness).toBe(0.6);
    expect(state.active_scene_id).toBe(3);
    expect(state.param_overrides).toEqual({ "2:x": 1 });
    expect(state.hype).toBe(0.9);
  });
});
