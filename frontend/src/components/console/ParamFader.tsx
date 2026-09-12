import { Fader } from "../controls/Fader";
import type { ControlAccent } from "../controls/Fader";

interface ParamFaderProps {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
  accent?: ControlAccent;
}

export function ParamFader({ label, min, max, value, onChange, accent = "cyan" }: ParamFaderProps) {
  return <Fader label={label} min={min} max={max} value={value} onChange={onChange} accent={accent} />;
}
