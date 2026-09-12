import { describe, expect, it } from "vitest";
import { harmonySwatches, hexToRgb, hsvToRgb, rgbToHex, rgbToHsv } from "./color";

describe("hsvToRgb / rgbToHsv", () => {
  it("round-trips primary hues", () => {
    for (const h of [0, 60, 120, 180, 240, 300]) {
      const rgb = hsvToRgb({ h, s: 1, v: 1 });
      const back = rgbToHsv(rgb);
      expect(back.h).toBeCloseTo(h === 360 ? 0 : h, 1);
      expect(back.s).toBeCloseTo(1, 5);
      expect(back.v).toBeCloseTo(1, 5);
    }
  });

  it("pure red is (1, 0, 0)", () => {
    expect(hsvToRgb({ h: 0, s: 1, v: 1 })).toEqual([1, 0, 0]);
  });

  it("zero saturation is a gray equal to value on every channel", () => {
    expect(hsvToRgb({ h: 200, s: 0, v: 0.5 })).toEqual([0.5, 0.5, 0.5]);
  });

  it("black has zero saturation and value regardless of hue", () => {
    expect(rgbToHsv([0, 0, 0])).toEqual({ h: 0, s: 0, v: 0 });
  });
});

describe("hex conversion", () => {
  it("round-trips through hex", () => {
    const rgb = hsvToRgb({ h: 280, s: 0.6, v: 0.8 });
    expect(hexToRgb(rgbToHex(rgb)).map((c) => Math.round(c * 255))).toEqual(
      rgb.map((c) => Math.round(c * 255)),
    );
  });

  it("white is #ffffff", () => {
    expect(rgbToHex([1, 1, 1])).toBe("#ffffff");
  });
});

describe("harmonySwatches", () => {
  it("returns one swatch per harmony offset, at the same saturation/value", () => {
    const base = { h: 40, s: 0.9, v: 0.7 };
    const swatches = harmonySwatches(base);
    // 1 complementary + 2 analogous + 2 triadic + 2 split-complementary.
    expect(swatches).toHaveLength(7);

    for (const { rgb } of swatches) {
      const hsv = rgbToHsv(rgb);
      expect(hsv.s).toBeCloseTo(base.s, 5);
      expect(hsv.v).toBeCloseTo(base.v, 5);
    }
  });

  it("the complementary swatch sits 180 degrees away in hue", () => {
    const base = { h: 40, s: 1, v: 1 };
    const complementary = harmonySwatches(base).find((s) => s.label === "Complementary")!;
    const hue = rgbToHsv(complementary.rgb).h;
    expect(hue).toBeCloseTo(220, 1);
  });
});
