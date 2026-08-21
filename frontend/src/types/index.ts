// TS mirrors of backend/src/lumen/api/schemas.py — keep in sync by hand, these
// are intentionally plain data shapes with no client-side business logic.

export type Point3 = [number, number, number];

export type DeviceSource = "mdns" | "scan" | "manual";

export interface Device {
  id: number;
  name: string;
  ip: string;
  mac: string | null;
  led_count: number;
  source: DeviceSource;
  online: boolean;
  last_seen: string | null;
}

export interface DeviceCreate {
  name: string;
  ip: string;
  led_count?: number;
}

export interface Fixture {
  id: number;
  name: string;
  device_id: number;
  start_channel: number;
  led_count: number;
  points: Point3[];
  reverse: boolean;
}

export type FixtureCreate = Omit<Fixture, "id">;
export type FixtureUpdate = Partial<FixtureCreate>;

export interface ExposedParam {
  node_id: string;
  param_key: string;
  label: string;
  min: number;
  max: number;
  default: number;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  sourceHandle?: string | null;
  target: string;
  targetHandle?: string | null;
}

export interface EffectGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Effect {
  id: number;
  name: string;
  description: string;
  graph: EffectGraph;
  exposed_params: ExposedParam[];
  updated_at: string;
}

export type EffectCreate = Omit<Effect, "id" | "updated_at">;
export type EffectUpdate = Partial<EffectCreate>;

export interface SceneAssignment {
  fixture_ids: number[] | "all";
  effect_id: number;
  params: Record<string, number>;
  brightness: number;
}

export interface Scene {
  id: number;
  name: string;
  assignments: SceneAssignment[];
  active: boolean;
}

export type SceneCreate = Omit<Scene, "id" | "active">;
export type SceneUpdate = Partial<Omit<Scene, "id">>;

export type NodeSocketType = "scalar" | "field" | "color";

export interface NodeSocket {
  key: string;
  type: NodeSocketType;
  label: string;
}

export interface NodeParam {
  key: string;
  type: "float" | "int" | "color" | "select";
  default: unknown;
  min?: number | null;
  max?: number | null;
  options?: string[] | null;
}

export interface NodeTypeDescriptor {
  type: string;
  category: string;
  label: string;
  inputs: NodeSocket[];
  outputs: NodeSocket[];
  params: NodeParam[];
}

export interface ConsoleState {
  master_brightness: number;
  active_scene_id: number | null;
  param_overrides: Record<string, number>;
  hype: number;
}

export interface PreviewRequest {
  graph: EffectGraph;
  led_count: number;
  length_meters?: number;
  param_overrides?: Record<string, number>;
}

export interface NodePreviewValue {
  socket_type: NodeSocketType;
  // scalar: length-1; field: one float per LED; color: one [r,g,b] (0-255) per LED.
  values: number[] | [number, number, number][];
}

export interface PreviewResponse {
  colors: [number, number, number][];
  nodes: Record<string, NodePreviewValue>;
  warning: string | null;
}
