import { useEffect, useState } from "react";
import type { ColorScheme, ColorSchemeCreate, ColorSchemeUpdate } from "../../types";
import { harmonySwatches, rgbToHex, rgbToHsv } from "../../utils/color";
import type { Rgb } from "../../utils/color";
import { ColorPicker } from "./ColorPicker";
import "./ColorSchemeEditor.css";

interface ColorSchemeEditorProps {
  scheme: ColorScheme | null;
  onSave: (payload: ColorSchemeCreate | ColorSchemeUpdate) => void;
  onCancel: () => void;
  onDelete?: () => void;
}

/** The "pretty cool color picker": an HSV picker plus a harmony suggestion
 * strip (complementary / analogous / triadic / split-complementary, computed
 * from whatever hue is on the picker right now) for assembling a palette a
 * few effects can all pull colors from -- see Scheme Color / Scheme Random
 * Color in the effect editor's node palette. */
export function ColorSchemeEditor({ scheme, onSave, onCancel, onDelete }: ColorSchemeEditorProps) {
  const [name, setName] = useState(scheme?.name ?? "New scheme");
  const [colors, setColors] = useState<Rgb[]>(scheme?.colors ?? []);
  const [draft, setDraft] = useState<Rgb>([1, 1, 1]);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    setName(scheme?.name ?? "New scheme");
    setColors(scheme?.colors ?? []);
    setSelected(null);
  }, [scheme]);

  function changeDraft(rgb: Rgb) {
    setDraft(rgb);
    // While a saved swatch is selected, dragging the picker edits it in place
    // instead of building up a separate, not-yet-added color.
    if (selected !== null) {
      setColors((prev) => prev.map((c, i) => (i === selected ? rgb : c)));
    }
  }

  function addDraft() {
    setColors((prev) => [...prev, draft]);
    setSelected(null);
  }

  function selectSwatch(index: number) {
    setSelected(index);
    setDraft(colors[index]);
  }

  function removeSwatch(index: number) {
    setColors((prev) => prev.filter((_, i) => i !== index));
    setSelected((current) => (current === index ? null : current));
  }

  const harmonies = harmonySwatches(rgbToHsv(draft));

  return (
    <div className="scheme-editor">
      <div className="scheme-editor__header">
        <input
          className="scheme-editor__name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Scheme name"
        />
        {onDelete && (
          <button type="button" className="btn btn--small btn--danger" onClick={onDelete}>
            Delete
          </button>
        )}
      </div>

      <div className="scheme-editor__body">
        <div className="scheme-editor__picker">
          <ColorPicker value={draft} onChange={changeDraft} />
          <button type="button" className="btn btn--small" onClick={addDraft}>
            {selected !== null ? "Add as new color" : "+ Add to scheme"}
          </button>

          <div className="scheme-editor__harmonies">
            <span className="section-label section-label--dim">Looks good with</span>
            <div className="scheme-editor__swatch-row">
              {harmonies.map((h, i) => (
                <button
                  key={i}
                  type="button"
                  className="scheme-editor__swatch scheme-editor__swatch--suggestion"
                  style={{ background: rgbToHex(h.rgb) }}
                  title={`${h.label} — click to add to the scheme`}
                  onClick={() => setColors((prev) => [...prev, h.rgb])}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="scheme-editor__colors">
          <span className="section-label section-label--dim">Colors ({colors.length})</span>
          <div className="scheme-editor__swatch-row scheme-editor__swatch-row--wrap">
            {colors.map((c, i) => (
              <div
                key={i}
                className={
                  "scheme-editor__swatch-wrap" +
                  (selected === i ? " scheme-editor__swatch-wrap--selected" : "")
                }
              >
                <button
                  type="button"
                  className="scheme-editor__swatch"
                  style={{ background: rgbToHex(c) }}
                  onClick={() => selectSwatch(i)}
                  title={`Color ${i + 1} — click to edit`}
                />
                <button
                  type="button"
                  className="scheme-editor__swatch-remove"
                  onClick={() => removeSwatch(i)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            ))}
            {colors.length === 0 && (
              <p className="scheme-editor__hint">
                No colors yet — pick one on the left and add it, or click a suggestion.
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="scheme-editor__footer">
        <button type="button" className="btn btn--small" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn--small btn--accent"
          disabled={colors.length === 0 || !name.trim()}
          onClick={() => onSave({ name: name.trim(), colors })}
        >
          Save
        </button>
      </div>
    </div>
  );
}
