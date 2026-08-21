import type { PreviewResponse } from "../../types";
import "./DebugBar.css";

interface DebugBarProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  ledCount: number;
  onLedCountChange: (count: number) => void;
  result: PreviewResponse | null;
  error: string | null;
}

export function DebugBar({ enabled, onToggle, ledCount, onLedCountChange, result, error }: DebugBarProps) {
  return (
    <div className={`debug-bar ${enabled ? "debug-bar--on" : ""}`}>
      <div className="debug-bar__controls">
        <button
          className={`btn btn--small ${enabled ? "btn--accent" : ""}`}
          onClick={() => onToggle(!enabled)}
        >
          {enabled ? "Debug: on" : "Debug: off"}
        </button>
        {enabled && (
          <label className="debug-bar__led-count">
            LEDs
            <input
              type="number"
              min={1}
              max={300}
              value={ledCount}
              onChange={(e) => onLedCountChange(Math.max(1, Math.min(300, Number(e.target.value))))}
            />
          </label>
        )}
        {enabled && !result && !error && <span className="debug-bar__hint">Evaluating…</span>}
        {error && <span className="debug-bar__error">{error}</span>}
        {result?.warning && <span className="debug-bar__warning">⚠ {result.warning}</span>}
      </div>

      {enabled && result && (
        <div className="debug-bar__strip" title="Live final LED Color output for a synthetic straight strip">
          {result.colors.map((c, i) => (
            <span key={i} className="debug-bar__led" style={{ background: `rgb(${c.join(",")})` }} />
          ))}
        </div>
      )}
    </div>
  );
}
