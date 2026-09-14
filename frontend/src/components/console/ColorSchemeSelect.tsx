import { useEffect } from "react";
import { useColorSchemeStore } from "../../store/useColorSchemeStore";
import { useConsoleStore } from "../../store/useConsoleStore";
import { rgbToHex } from "../../utils/color";
import "./ColorSchemeSelect.css";

const NONE_VALUE = "";

/** Lets the live console pick which saved ColorScheme every Scheme Color /
 * Scheme Random Color node reads from -- the same override edited on the
 * Colors page, surfaced here too so a show doesn't need a tab switch to
 * change palette mid-set. */
export function ColorSchemeSelect() {
  const schemes = useColorSchemeStore((s) => s.schemes);
  const refresh = useColorSchemeStore((s) => s.refresh);
  const activeSchemeId = useConsoleStore((s) => s.active_color_scheme_id);
  const setColorScheme = useConsoleStore((s) => s.setColorScheme);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const active = schemes.find((s) => s.id === activeSchemeId) ?? null;

  return (
    <div className="color-scheme-select">
      <div className="console-card__sublabel">Color scheme</div>
      <div className="color-scheme-select__row">
        {active && active.colors.length > 0 ? (
          <div className="color-scheme-select__swatches">
            {active.colors.map((c, i) => (
              <span key={i} className="color-scheme-select__swatch" style={{ background: rgbToHex(c) }} />
            ))}
          </div>
        ) : (
          <div className="color-scheme-select__swatches color-scheme-select__swatches--empty" />
        )}
        <select
          className="color-scheme-select__input"
          value={activeSchemeId != null ? String(activeSchemeId) : NONE_VALUE}
          onChange={(e) => setColorScheme(e.target.value === NONE_VALUE ? null : Number(e.target.value))}
        >
          <option value={NONE_VALUE}>None (white)</option>
          {schemes.map((scheme) => (
            <option key={scheme.id} value={scheme.id}>
              {scheme.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
