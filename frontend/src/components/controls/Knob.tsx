import { useCallback, useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { ControlAccent } from "./Fader";
import "./controls.css";

interface KnobProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  step?: number;
  accent?: ControlAccent;
  format?: (value: number) => string;
}

const SWEEP = 270; // degrees of usable travel, centred at 12 o'clock
const START = -135;
// Pixels of vertical drag to travel the whole range.
const DRAG_RANGE_PX = 160;

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function arcPath(cx: number, cy: number, r: number, fromDeg: number, toDeg: number): string {
  const [x1, y1] = polar(cx, cy, r, fromDeg);
  const [x2, y2] = polar(cx, cy, r, toDeg);
  const large = toDeg - fromDeg > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}

// A rotary pot: drag up/down to turn it. The filled arc and the pointer line
// both track the value; brightness on the arc is glow, per the house rules.
export function Knob({ label, value, min, max, onChange, step, accent = "cyan", format }: KnobProps) {
  const dragRef = useRef<{ startY: number; startValue: number } | null>(null);
  const span = max - min || 1;
  const fraction = Math.max(0, Math.min(1, (value - min) / span));
  const angle = START + fraction * SWEEP;
  const display = format ? format(value) : Number.isInteger(step) ? String(Math.round(value)) : value.toFixed(2);

  const apply = useCallback(
    (raw: number) => {
      let next = Math.max(min, Math.min(max, raw));
      if (step) next = Math.round(next / step) * step;
      onChange(next);
    },
    [min, max, step, onChange],
  );

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      dragRef.current = { startY: e.clientY, startValue: value };
    },
    [value],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag) return;
      const delta = (drag.startY - e.clientY) / DRAG_RANGE_PX;
      apply(drag.startValue + delta * span);
    },
    [apply, span],
  );

  const endDrag = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  return (
    <div className={`knob knob--${accent}`}>
      <div
        className="knob__dial"
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={min}
        aria-valuemax={max}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={(e) => {
          const inc = step || span / 50;
          if (e.key === "ArrowUp" || e.key === "ArrowRight") apply(value + inc);
          else if (e.key === "ArrowDown" || e.key === "ArrowLeft") apply(value - inc);
        }}
      >
        <svg viewBox="0 0 48 48" className="knob__svg">
          <path d={arcPath(24, 24, 19, START, START + SWEEP)} className="knob__arc-track" />
          {fraction > 0 && <path d={arcPath(24, 24, 19, START, angle)} className="knob__arc" />}
          <circle cx="24" cy="24" r="14" className="knob__body" />
          <g transform={`rotate(${angle} 24 24)`}>
            <line x1="24" y1="24" x2="24" y2="12" className="knob__indicator" />
          </g>
        </svg>
      </div>
      <span className="knob__value">{display}</span>
      <span className="knob__label">{label}</span>
    </div>
  );
}
