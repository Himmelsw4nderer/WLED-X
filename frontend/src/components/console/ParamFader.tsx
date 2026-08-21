import { useThrottledSlider } from "./useThrottledSlider";

interface ParamFaderProps {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
}

export function ParamFader({ label, min, max, value, onChange }: ParamFaderProps) {
  const { local, onChange: handleChange, onDragStart, onDragEnd } = useThrottledSlider(value, onChange);
  const step = (max - min) / 200 || 0.01;

  return (
    <div className="param-fader">
      <div className="param-fader__head">
        <span className="param-fader__label">{label}</span>
        <span className="param-fader__value">{local.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={local}
        onChange={(e) => handleChange(Number(e.target.value))}
        onPointerDown={onDragStart}
        onPointerUp={onDragEnd}
      />
    </div>
  );
}
