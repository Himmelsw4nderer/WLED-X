import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEffectStore } from "../store/useEffectStore";
import type { Effect } from "../types";
import "./EffectsListPage.css";

function formatUpdatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function EffectsListPage() {
  const { effects, loading, refresh, add, update, remove } = useEffectStore();
  const navigate = useNavigate();

  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function createEffect() {
    setCreating(true);
    setError(null);
    try {
      const effect = await add({
        name: "New Effect",
        description: "",
        graph: { nodes: [], edges: [] },
        exposed_params: [],
      });
      navigate(`/effects/${effect.id}`);
    } catch {
      setError("Failed to create effect.");
    } finally {
      setCreating(false);
    }
  }

  function startRename(effect: Effect) {
    setRenamingId(effect.id);
    setRenameValue(effect.name);
  }

  async function commitRename(effect: Effect) {
    const trimmed = renameValue.trim();
    setRenamingId(null);
    if (!trimmed || trimmed === effect.name) return;
    try {
      await update(effect.id, { name: trimmed });
    } catch {
      setError(`Failed to rename "${effect.name}".`);
    }
  }

  async function deleteEffect(effect: Effect) {
    try {
      await remove(effect.id);
    } catch {
      setError(`Failed to delete "${effect.name}".`);
    }
  }

  return (
    <div className="page effects-page">
      <header className="effects-page__header">
        <h1>Effects</h1>
        <button className="btn btn--accent" onClick={() => void createEffect()} disabled={creating}>
          {creating ? "Creating…" : "New effect"}
        </button>
      </header>

      {error && <div className="banner banner--error">{error}</div>}

      {loading && effects.length === 0 ? (
        <p className="effects-page__empty">Loading…</p>
      ) : effects.length === 0 ? (
        <p className="effects-page__empty">No effects yet. Create one to start building a node graph.</p>
      ) : (
        <ul className="effect-list">
          {effects.map((effect) => (
            <li key={effect.id} className="effect-row">
              <div className="effect-row__main" onClick={() => navigate(`/effects/${effect.id}`)}>
                {renamingId === effect.id ? (
                  <input
                    className="effect-row__rename-input"
                    autoFocus
                    value={renameValue}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => void commitRename(effect)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.currentTarget.blur();
                      if (e.key === "Escape") setRenamingId(null);
                    }}
                  />
                ) : (
                  <span className="effect-row__name">{effect.name}</span>
                )}
                {effect.description && <span className="effect-row__description">{effect.description}</span>}
                <span className="effect-row__meta">
                  {effect.graph.nodes.length} nodes · {effect.graph.edges.length} edges · updated{" "}
                  {formatUpdatedAt(effect.updated_at)}
                </span>
              </div>
              <div className="effect-row__actions">
                <button
                  className="btn btn--small"
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(effect);
                  }}
                >
                  Rename
                </button>
                <button
                  className="btn btn--small btn--danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    void deleteEffect(effect);
                  }}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
