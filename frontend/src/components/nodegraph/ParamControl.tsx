import { useState } from "react";
import type { NodeParam } from "../../types";
import "./ParamControl.css";

interface ParamControlProps {
  param: NodeParam;
  value: unknown;
  compact?: boolean;
  exposed: boolean;
  onChange: (value: unknown) => void;
  onToggleExposed: () => void;
}

function isRgbTriple(value: unknown): value is [number, number, number] {
  return Array.isArray(value) && value.length === 3 && value.every((v) => typeof v === "number");
}

function toHex(rgb: [number, number, number]): string {
  const channel = (v: number) =>
    Math.round(Math.min(1, Math.max(0, v)) * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${channel(rgb[0])}${channel(rgb[1])}${channel(rgb[2])}`;
}

function fromHex(hex: string): [number, number, number] {
  const n = Number.parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function JsonFallback({ value, onChange }: { value: unknown; onChange: (value: unknown) => void }) {
  const [text, setText] = useState(() => JSON.stringify(value));
  const [invalid, setInvalid] = useState(false);

  return (
    <textarea
      className={`param-control__json nodrag nowheel ${invalid ? "param-control__json--invalid" : ""}`}
      rows={2}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        try {
          onChange(JSON.parse(text) as unknown);
          setInvalid(false);
        } catch {
          setInvalid(true);
        }
      }}
    />
  );
}

function ParamInput({
  param,
  value,
  onChange,
}: {
  param: NodeParam;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (param.type === "select") {
    const current =
      typeof value === "string" ? value : typeof param.default === "string" ? param.default : (param.options?.[0] ?? "");
    return (
      <select
        className="param-control__input nodrag nowheel"
        value={current}
        onChange={(e) => onChange(e.target.value)}
      >
        {(param.options ?? []).map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  if (param.type === "color") {
    const rgb = isRgbTriple(value) ? value : isRgbTriple(param.default) ? param.default : null;
    if (rgb) {
      return (
        <input
          className="param-control__color nodrag nowheel"
          type="color"
          value={toHex(rgb)}
          onChange={(e) => onChange(fromHex(e.target.value))}
        />
      );
    }
    return <JsonFallback value={value ?? param.default} onChange={onChange} />;
  }

  const numeric = typeof value === "number" ? value : typeof param.default === "number" ? param.default : 0;
  const step = param.type === "int" ? 1 : 0.01;
  return (
    <input
      className="param-control__input nodrag nowheel"
      type="number"
      value={numeric}
      step={step}
      min={typeof param.min === "number" ? param.min : undefined}
      max={typeof param.max === "number" ? param.max : undefined}
      onChange={(e) => {
        const raw = Number(e.target.value);
        onChange(param.type === "int" ? Math.round(raw) : raw);
      }}
    />
  );
}

export function ParamControl({ param, value, compact, exposed, onChange, onToggleExposed }: ParamControlProps) {
  const canExpose = param.type === "float" || param.type === "int";

  return (
    <div className={`param-control ${compact ? "param-control--compact" : ""}`}>
      <ParamInput param={param} value={value} onChange={onChange} />
      {canExpose && (
        <button
          type="button"
          className={`param-control__pin nodrag ${exposed ? "param-control__pin--active" : ""}`}
          title={exposed ? "Remove from console" : "Expose to console"}
          aria-pressed={exposed}
          onClick={onToggleExposed}
        >
          ●
        </button>
      )}
    </div>
  );
}
