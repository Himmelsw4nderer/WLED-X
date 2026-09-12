// RGB channels are 0..1 floats throughout (matching the backend's color
// convention -- see wled_x/effects/nodes/color_nodes.py); HSV hue is degrees
// 0..360, saturation/value are 0..1.

export interface Hsv {
  h: number;
  s: number;
  v: number;
}

export type Rgb = [number, number, number];

export function hsvToRgb({ h, s, v }: Hsv): Rgb {
  const hue = ((h % 360) + 360) % 360;
  const c = v * s;
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1));
  const m = v - c;
  let [r, g, b] = [0, 0, 0];
  if (hue < 60) [r, g, b] = [c, x, 0];
  else if (hue < 120) [r, g, b] = [x, c, 0];
  else if (hue < 180) [r, g, b] = [0, c, x];
  else if (hue < 240) [r, g, b] = [0, x, c];
  else if (hue < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + m, g + m, b + m];
}

export function rgbToHsv([r, g, b]: Rgb): Hsv {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  let h = 0;
  if (delta !== 0) {
    if (max === r) h = 60 * (((g - b) / delta) % 6);
    else if (max === g) h = 60 * ((b - r) / delta + 2);
    else h = 60 * ((r - g) / delta + 4);
  }
  if (h < 0) h += 360;
  const s = max === 0 ? 0 : delta / max;
  return { h, s, v: max };
}

export function rgbToHex([r, g, b]: Rgb): string {
  const channel = (v: number) =>
    Math.round(Math.min(1, Math.max(0, v)) * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

export function hexToRgb(hex: string): Rgb {
  const n = Number.parseInt(hex.replace("#", ""), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// Common harmony offsets (degrees of hue rotation) for a "pick colors that
// look good together" suggestion strip -- each is applied at the current
// swatch's own saturation/value so a suggestion always reads as "the same
// color family, different hue".
export const HARMONY_OFFSETS: { label: string; degrees: number[] }[] = [
  { label: "Complementary", degrees: [180] },
  { label: "Analogous", degrees: [-30, 30] },
  { label: "Triadic", degrees: [120, 240] },
  { label: "Split-complementary", degrees: [150, 210] },
];

export function harmonySwatches(base: Hsv): { label: string; rgb: Rgb }[] {
  const out: { label: string; rgb: Rgb }[] = [];
  for (const { label, degrees } of HARMONY_OFFSETS) {
    for (const degrees_ of degrees) {
      out.push({ label, rgb: hsvToRgb({ h: base.h + degrees_, s: base.s, v: base.v }) });
    }
  }
  return out;
}
