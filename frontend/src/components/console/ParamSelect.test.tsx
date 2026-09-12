import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ParamSelect } from "./ParamSelect";

describe("ParamSelect", () => {
  it("renders the label and every option, with the current value selected", () => {
    render(
      <ParamSelect label="Sweep Axis" options={["x", "y", "z", "xz"]} value="z" onChange={vi.fn()} />,
    );
    expect(screen.getByText("Sweep Axis")).toBeInTheDocument();
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("z");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["x", "y", "z", "xz"]);
  });

  it("emits the chosen option string on change", () => {
    const onChange = vi.fn();
    render(
      <ParamSelect label="Sweep Axis" options={["x", "y", "z"]} value="x" onChange={onChange} />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "y" } });
    expect(onChange).toHaveBeenCalledWith("y");
  });
});
