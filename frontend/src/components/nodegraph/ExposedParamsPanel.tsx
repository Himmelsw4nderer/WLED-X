import type { ExposedParam } from "../../types";
import "./ExposedParamsPanel.css";

interface ExposedParamsPanelProps {
  params: ExposedParam[];
  onUpdate: (index: number, patch: Partial<ExposedParam>) => void;
  onRemove: (index: number) => void;
}

export function ExposedParamsPanel({ params, onUpdate, onRemove }: ExposedParamsPanelProps) {
  return (
    <aside className="exposed-params-panel">
      <div className="exposed-params-panel__title">Console-exposed params</div>
      {params.length === 0 ? (
        <p className="exposed-params-panel__empty">
          Pin a numeric param on a node to expose it as a slider in the live console.
        </p>
      ) : (
        <ul className="exposed-params-panel__list">
          {params.map((p, index) => (
            <li key={`${p.node_id}:${p.param_key}`} className="exposed-params-panel__row">
              <div className="exposed-params-panel__source" title={`${p.node_id} · ${p.param_key}`}>
                {p.node_id} · {p.param_key}
              </div>
              <input
                className="exposed-params-panel__label"
                value={p.label}
                onChange={(e) => onUpdate(index, { label: e.target.value })}
              />
              <div className="exposed-params-panel__minmax">
                <input
                  type="number"
                  value={p.min}
                  onChange={(e) => onUpdate(index, { min: Number(e.target.value) })}
                />
                <span>to</span>
                <input
                  type="number"
                  value={p.max}
                  onChange={(e) => onUpdate(index, { max: Number(e.target.value) })}
                />
              </div>
              <button className="btn btn--small btn--danger" onClick={() => onRemove(index)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
