import "./ParamSelect.css";

interface ParamSelectProps {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

// The dropdown sibling of ParamFader: a console channel for a node's select
// param (e.g. Position's axis / space) so it can be switched live without
// reopening the effect editor.
export function ParamSelect({ label, options, value, onChange }: ParamSelectProps) {
  return (
    <div className="param-select">
      <select
        className="param-select__input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
      <span className="param-select__label">{label}</span>
    </div>
  );
}
