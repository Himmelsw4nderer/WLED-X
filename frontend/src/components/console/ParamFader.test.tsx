import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ParamFader } from "./ParamFader";

function flushAnimationFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

describe("ParamFader", () => {
  it("renders the label and current value", () => {
    render(<ParamFader label="Speed" min={0} max={10} value={3} onChange={vi.fn()} />);
    expect(screen.getByText("Speed")).toBeInTheDocument();
    expect(screen.getByText("3.00")).toBeInTheDocument();
  });

  it("updates the displayed value immediately and commits the change after a frame", async () => {
    const onChange = vi.fn();
    render(<ParamFader label="Speed" min={0} max={10} value={1} onChange={onChange} />);

    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "5" } });

    expect(screen.getByText("5.00")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();

    await flushAnimationFrame();

    expect(onChange).toHaveBeenCalledWith(5);
  });

  it("tracks external value changes when the user isn't dragging", () => {
    const { rerender } = render(
      <ParamFader label="Speed" min={0} max={10} value={1} onChange={vi.fn()} />,
    );
    rerender(<ParamFader label="Speed" min={0} max={10} value={7} onChange={vi.fn()} />);
    expect(screen.getByText("7.00")).toBeInTheDocument();
  });
});
