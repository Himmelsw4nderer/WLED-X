import { Fader } from "../controls/Fader";

interface MasterFaderProps {
  value: number;
  onChange: (value: number) => void;
}

export function MasterFader({ value, onChange }: MasterFaderProps) {
  return (
    <div className="master-fader">
      <Fader
        label="Grand"
        value={value}
        min={0}
        max={1}
        onChange={onChange}
        size="lg"
        accent="accent"
        format={(v) => `${Math.round(v * 100)}%`}
      />
    </div>
  );
}
