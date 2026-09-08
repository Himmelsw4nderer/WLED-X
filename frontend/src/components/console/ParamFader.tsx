import { Fader } from "../controls/Fader";

interface ParamFaderProps {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
}

export function ParamFader({ label, min, max, value, onChange }: ParamFaderProps) {
  return <Fader label={label} min={min} max={max} value={value} onChange={onChange} accent="cyan" />;
}
