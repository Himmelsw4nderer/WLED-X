import { useEffect, useState } from "react";
import { ColorSchemeEditor } from "../components/colorscheme/ColorSchemeEditor";
import { useColorSchemeStore } from "../store/useColorSchemeStore";
import { useConsoleStore } from "../store/useConsoleStore";
import { rgbToHex } from "../utils/color";
import type { ColorScheme, ColorSchemeCreate, ColorSchemeUpdate } from "../types";
import "./ColorSchemesPage.css";

type EditorState = { mode: "create" } | { mode: "edit"; scheme: ColorScheme };

export function ColorSchemesPage() {
  const schemes = useColorSchemeStore((s) => s.schemes);
  const refresh = useColorSchemeStore((s) => s.refresh);
  const add = useColorSchemeStore((s) => s.add);
  const update = useColorSchemeStore((s) => s.update);
  const remove = useColorSchemeStore((s) => s.remove);

  const connect = useConsoleStore((s) => s.connect);
  const activeSchemeId = useConsoleStore((s) => s.active_color_scheme_id);
  const setColorScheme = useConsoleStore((s) => s.setColorScheme);

  const [editorState, setEditorState] = useState<EditorState | null>(null);

  useEffect(() => {
    connect();
    void refresh();
  }, [connect, refresh]);

  async function handleSave(payload: ColorSchemeCreate | ColorSchemeUpdate) {
    if (editorState?.mode === "edit") {
      await update(editorState.scheme.id, payload);
    } else {
      await add(payload as ColorSchemeCreate);
    }
    setEditorState(null);
  }

  async function handleDelete(id: number) {
    await remove(id);
    if (activeSchemeId === id) setColorScheme(null);
    setEditorState(null);
  }

  return (
    <div className="page color-schemes-page">
      <div className="color-schemes-page__header">
        <h1>Color Schemes</h1>
        <button className="btn btn--accent" onClick={() => setEditorState({ mode: "create" })}>
          + New scheme
        </button>
      </div>

      <p className="color-schemes-page__hint">
        Build a palette here, then pull from it in an effect graph with the Scheme Color / Scheme
        Random Color nodes. Activating a scheme overrides those nodes across every effect at once —
        pair with a Brightness node for per-pixel dimming.
      </p>

      {schemes.length === 0 && <p className="color-schemes-page__hint">No color schemes yet.</p>}

      <div className="color-schemes-page__grid">
        {schemes.map((scheme) => {
          const live = scheme.id === activeSchemeId;
          return (
            <div key={scheme.id} className={`panel color-scheme-card ${live ? "color-scheme-card--live" : ""}`}>
              {scheme.colors.length > 0 ? (
                <div className="color-scheme-card__swatches">
                  {scheme.colors.map((c, i) => (
                    <span key={i} className="color-scheme-card__swatch" style={{ background: rgbToHex(c) }} />
                  ))}
                </div>
              ) : (
                <div className="color-scheme-card__swatches color-scheme-card__swatches--empty" />
              )}

              <div className="color-scheme-card__title-row">
                <strong>{scheme.name}</strong>
                {live && <span className="badge badge--live">Live</span>}
              </div>

              <div className="color-scheme-card__actions">
                <button
                  className={`btn btn--small ${live ? "btn--accent" : ""}`}
                  onClick={() => setColorScheme(live ? null : scheme.id)}
                >
                  {live ? "Deactivate" : "Activate"}
                </button>
                <button className="btn btn--small" onClick={() => setEditorState({ mode: "edit", scheme })}>
                  Edit
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {editorState && (
        <div className="color-schemes-page__modal">
          <ColorSchemeEditor
            scheme={editorState.mode === "edit" ? editorState.scheme : null}
            onSave={(payload) => void handleSave(payload)}
            onCancel={() => setEditorState(null)}
            onDelete={
              editorState.mode === "edit" ? () => void handleDelete(editorState.scheme.id) : undefined
            }
          />
        </div>
      )}
    </div>
  );
}
