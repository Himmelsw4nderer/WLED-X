import type { NodePreviewValue } from "../../types";
import "./NodePreviewBadge.css";

interface NodePreviewBadgeProps {
  preview: NodePreviewValue;
}

// Deliberately does NOT auto-normalize field values to their own min/max --
// that would make a broken, constant-zero field "look" like it varies just
// because it's being stretched to fill the bar. Values are clamped to the
// conceptual 0..1 range everything in this system uses, so a flat field
// (like the bug this whole debug mode exists to catch) renders as a flat
// black bar, not a lie.
export function NodePreviewBadge({ preview }: NodePreviewBadgeProps) {
  if (preview.socket_type === "scalar") {
    const value = (preview.values[0] as number) ?? 0;
    return <span className="node-preview-badge node-preview-badge--scalar">{value.toFixed(3)}</span>;
  }

  if (preview.socket_type === "color") {
    const rgb = preview.values as [number, number, number][];
    return (
      <span
        className="node-preview-badge node-preview-badge--bar"
        style={{ background: gradientFromRgb(rgb) }}
        title={rgb.length ? `rgb(${rgb[0].join(",")}) … rgb(${rgb[rgb.length - 1].join(",")})` : ""}
      />
    );
  }

  const values = preview.values as number[];
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  return (
    <span className="node-preview-badge node-preview-badge--field-wrap">
      <span
        className="node-preview-badge node-preview-badge--bar"
        style={{ background: gradientFromField(values) }}
      />
      <span className="node-preview-badge__range">
        {min.toFixed(2)}…{max.toFixed(2)}
      </span>
    </span>
  );
}

function gradientFromRgb(rgb: [number, number, number][]): string {
  if (rgb.length === 0) return "#000";
  if (rgb.length === 1) return `rgb(${rgb[0].join(",")})`;
  const stops = rgb.map((c, i) => `rgb(${c.join(",")}) ${(i / (rgb.length - 1)) * 100}%`);
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

function gradientFromField(values: number[]): string {
  if (values.length === 0) return "#000";
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  const stops = values.map((v, i) => {
    const g = Math.round(clamp(v) * 255);
    const pos = values.length === 1 ? 0 : (i / (values.length - 1)) * 100;
    return `rgb(${g},${g},${g}) ${pos}%`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}
