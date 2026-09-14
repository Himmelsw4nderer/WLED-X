import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { hexToRgb, hsvToRgb, rgbToHex, rgbToHsv } from "../../utils/color";
import type { Rgb } from "../../utils/color";
import "./ColorPicker.css";

interface ColorPickerProps {
  value: Rgb;
  onChange: (rgb: Rgb) => void;
}

// Hex text is edited locally and only committed on blur/Enter -- a controlled
// input driven straight off `rgbToHex(value)` would snap back to the last
// committed color after every keystroke of an in-progress edit.
function HexField({ value, onChange }: ColorPickerProps) {
  const [text, setText] = useState(() => rgbToHex(value));
  useEffect(() => setText(rgbToHex(value)), [value]);

  function commit() {
    if (/^#[0-9a-fA-F]{6}$/.test(text)) onChange(hexToRgb(text));
    else setText(rgbToHex(value));
  }

  return (
    <input
      className="color-picker__hex"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
    />
  );
}

/** A compact HSV picker: a saturation/value square under a hue slider, plus a
 * hex field and native color input for quick/precise entry. No canvas or
 * external library -- just two pointer-draggable divs and CSS gradients. */
export function ColorPicker({ value, onChange }: ColorPickerProps) {
  const hsv = rgbToHsv(value);
  const svRef = useRef<HTMLDivElement>(null);
  const hueRef = useRef<HTMLDivElement>(null);

  const updateFromSv = useCallback(
    (clientX: number, clientY: number) => {
      const rect = svRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);
      const y = Math.min(Math.max(clientY - rect.top, 0), rect.height);
      onChange(hsvToRgb({ h: hsv.h, s: x / rect.width, v: 1 - y / rect.height }));
    },
    [hsv.h, onChange],
  );

  const updateFromHue = useCallback(
    (clientX: number) => {
      const rect = hueRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);
      // A picker parked at s=0 or v=0 (pure white/black) has no visible hue to
      // nudge -- pin s/v to 1 in that case so dragging the hue bar still shows
      // an immediate, visible color change.
      onChange(hsvToRgb({ h: (x / rect.width) * 360, s: hsv.s || 1, v: hsv.v || 1 }));
    },
    [hsv.s, hsv.v, onChange],
  );

  function svPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    updateFromSv(e.clientX, e.clientY);
  }
  function svPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if ((e.buttons & 1) === 0) return;
    updateFromSv(e.clientX, e.clientY);
  }
  function huePointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    updateFromHue(e.clientX);
  }
  function huePointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if ((e.buttons & 1) === 0) return;
    updateFromHue(e.clientX);
  }

  const hueColor = rgbToHex(hsvToRgb({ h: hsv.h, s: 1, v: 1 }));

  return (
    <div className="color-picker">
      <div
        ref={svRef}
        className="color-picker__sv"
        style={{ backgroundColor: hueColor }}
        onPointerDown={svPointerDown}
        onPointerMove={svPointerMove}
      >
        <span
          className="color-picker__sv-cursor"
          style={{ left: `${hsv.s * 100}%`, top: `${(1 - hsv.v) * 100}%` }}
        />
      </div>

      <div ref={hueRef} className="color-picker__hue" onPointerDown={huePointerDown} onPointerMove={huePointerMove}>
        <span className="color-picker__hue-cursor" style={{ left: `${(hsv.h / 360) * 100}%` }} />
      </div>

      <div className="color-picker__row">
        <span className="color-picker__swatch" style={{ background: rgbToHex(value) }} />
        <HexField value={value} onChange={onChange} />
        <input
          className="color-picker__native"
          type="color"
          value={rgbToHex(value)}
          onChange={(e) => onChange(hexToRgb(e.target.value))}
        />
      </div>
    </div>
  );
}
