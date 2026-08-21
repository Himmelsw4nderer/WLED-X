import { useThrottledSlider } from "./useThrottledSlider";

interface MasterFaderProps {
  value: number;
  onChange: (value: number) => void;
}

export function MasterFader({ value, onChange }: MasterFaderProps) {
  const { local, onChange: handleChange, onDragStart, onDragEnd } = useThrottledSlider(value, onChange);

  return (
    <div className="master-fader">
      <div className="master-fader__head">
        <span>Master</span>
        <span className="master-fader__value">{Math.round(local * 100)}%</span>
      </div>
      <input
        type="range"
        className="master-fader__input"
        min={0}
        max={1}
        step={0.01}
        value={local}
        onChange={(e) => handleChange(Number(e.target.value))}
        onPointerDown={onDragStart}
        onPointerUp={onDragEnd}
      />
    </div>
  );
}
