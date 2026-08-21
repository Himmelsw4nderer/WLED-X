import type { Node } from "reactflow";
import { describe, expect, it } from "vitest";
import {
  createNodeId,
  defaultDataForDescriptor,
  isValidSocketConnection,
  makeEdgeId,
} from "./graphUtils";
import type { NodeTypeDescriptor } from "../../types";

function descriptor(overrides: Partial<NodeTypeDescriptor>): NodeTypeDescriptor {
  return {
    type: "test_node",
    category: "test",
    label: "Test Node",
    inputs: [],
    outputs: [],
    params: [],
    ...overrides,
  };
}

describe("createNodeId", () => {
  it("prefixes the id with the node type", () => {
    expect(createNodeId("audio_level")).toMatch(/^audio_level-/);
  });

  it("never produces the same id twice", () => {
    const ids = new Set(Array.from({ length: 50 }, () => createNodeId("noise")));
    expect(ids.size).toBe(50);
  });
});

describe("makeEdgeId", () => {
  it("embeds source/target node and handle in the id", () => {
    const id = makeEdgeId({ source: "a", sourceHandle: "value", target: "b", targetHandle: "h" });
    expect(id).toContain("a");
    expect(id).toContain("value");
    expect(id).toContain("b");
    expect(id).toContain("h");
  });

  it("falls back to placeholders for missing handles", () => {
    const id = makeEdgeId({ source: "a", sourceHandle: null, target: "b", targetHandle: null });
    expect(id).toContain("out");
    expect(id).toContain("in");
  });
});

describe("defaultDataForDescriptor", () => {
  it("seeds one entry per param from its default", () => {
    const d = descriptor({
      params: [
        { key: "speed", type: "float", default: 1.5 },
        { key: "band", type: "select", default: "low", options: ["low", "mid", "high"] },
      ],
    });
    expect(defaultDataForDescriptor(d)).toEqual({ speed: 1.5, band: "low" });
  });

  it("deep-clones object/array defaults so nodes don't share references", () => {
    const stops = [{ pos: 0, color: [0, 0, 0] }];
    const d = descriptor({ params: [{ key: "stops", type: "color", default: stops }] });
    const a = defaultDataForDescriptor(d);
    const b = defaultDataForDescriptor(d);
    expect(a.stops).toEqual(stops);
    expect(a.stops).not.toBe(stops);
    expect(a.stops).not.toBe(b.stops);
  });
});

describe("isValidSocketConnection", () => {
  const posNode: Node = { id: "pos", type: "position_x", position: { x: 0, y: 0 }, data: {} };
  const hsvNode: Node = { id: "hsv", type: "hsv", position: { x: 0, y: 0 }, data: {} };
  const rampNode: Node = { id: "ramp", type: "color_ramp", position: { x: 0, y: 0 }, data: {} };
  const nodes = [posNode, hsvNode, rampNode];

  const descriptorsByType = new Map<string, NodeTypeDescriptor>([
    [
      "position_x",
      descriptor({ type: "position_x", outputs: [{ key: "value", type: "field", label: "Position X" }] }),
    ],
    [
      "hsv",
      descriptor({
        type: "hsv",
        inputs: [{ key: "h", type: "field", label: "H" }],
        outputs: [{ key: "value", type: "color", label: "Color" }],
      }),
    ],
    [
      "color_ramp",
      descriptor({ type: "color_ramp", inputs: [{ key: "position", type: "field", label: "Position" }] }),
    ],
  ]);

  it("allows a field output into a field input", () => {
    expect(
      isValidSocketConnection(
        { source: "pos", sourceHandle: "value", target: "ramp", targetHandle: "position" },
        nodes,
        descriptorsByType,
      ),
    ).toBe(true);
  });

  it("allows a scalar/field source feeding a color-producing node's field input", () => {
    expect(
      isValidSocketConnection(
        { source: "pos", sourceHandle: "value", target: "hsv", targetHandle: "h" },
        nodes,
        descriptorsByType,
      ),
    ).toBe(true);
  });

  it("rejects a color output feeding a field input", () => {
    expect(
      isValidSocketConnection(
        { source: "hsv", sourceHandle: "value", target: "ramp", targetHandle: "position" },
        nodes,
        descriptorsByType,
      ),
    ).toBe(false);
  });

  it("is permissive when either endpoint's type can't be resolved", () => {
    expect(
      isValidSocketConnection(
        { source: "missing", sourceHandle: "x", target: "ramp", targetHandle: "position" },
        nodes,
        descriptorsByType,
      ),
    ).toBe(true);
  });
});
