import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { NodeTypeDescriptor } from "../../types";
import { NodePalette } from "./NodePalette";

function descriptor(over: Partial<NodeTypeDescriptor>): NodeTypeDescriptor {
  return {
    type: "x",
    category: "spatial",
    label: "X",
    inputs: [],
    outputs: [],
    params: [],
    ...over,
  };
}

describe("NodePalette", () => {
  it("lists non-deprecated node types but hides deprecated ones", () => {
    render(
      <NodePalette
        descriptors={[
          descriptor({ type: "position", label: "Position" }),
          descriptor({ type: "position_x", label: "Position X", deprecated: true }),
          descriptor({ type: "distance_from_origin", label: "Distance From Origin", deprecated: true }),
        ]}
      />,
    );

    expect(screen.getByText("Position")).toBeInTheDocument();
    expect(screen.queryByText("Position X")).not.toBeInTheDocument();
    expect(screen.queryByText("Distance From Origin")).not.toBeInTheDocument();
  });
});
