import type { CSSProperties } from "react";
import { useThrottledSlider } from "../console/useThrottledSlider";
import "./controls.css";

export type ControlAccent = "accent" | "cyan" | "lime" | "gold" | "violet" | "ember";

interface FaderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  accent?: ControlAccent;
  /** Custom value readout; defaults to two decimal places. */
  format?: (value: number) => string;
  size?: "sm" | "md" | "lg";
  ticks?: number;
}

// A real channel-strip fader: a recessed track with tick marks, a glowing fill
// below a chunky bezelled cap, a tabular readout and a Silkscreen legend. The
// range input is kept (transparent, on top) so it stays keyboard- and
// screen-reader-accessible -- the visible parts are drawn from `local`.
export function Fader({
  label,
  value,
  min,
  max,
  onChange,
  accent = "accent",
  format,
  size = "md",
  ticks = 9,
}: FaderProps) {
  const { local, onChange: handleChange, onDragStart, onDragEnd } = useThrottledSlider(value, onChange);
  const step = (max - min) / 200 || 0.01;
  const pct = max === min ? 0 : ((local - min) / (max - min)) * 100;
  const display = format ? format(local) : local.toFixed(2);

  return (
    <div className={`fader fader--${size} fader--${accent}`}>
      <span className="fader__value">{display}</span>
      <div className="fader__slot" style={{ "--fader-pct": `${pct}%` } as CSSProperties}>
        <div className="fader__ticks" aria-hidden="true">
          {Array.from({ length: ticks }, (_, i) => (
            <span key={i} />
          ))}
        </div>
        <div className="fader__track well">
          <div className="fader__fill" />
        </div>
        <div className="fader__cap" />
        <input
          className="fader__input"
          type="range"
          min={min}
          max={max}
          step={step}
          value={local}
          onChange={(e) => handleChange(Number(e.target.value))}
          onPointerDown={onDragStart}
          onPointerUp={onDragEnd}
          aria-label={label}
        />
      </div>
      <span className="fader__label">{label}</span>
    </div>
  );
}
