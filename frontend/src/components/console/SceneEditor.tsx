import { useState } from "react";
import type { FormEvent } from "react";
import type { Effect, Fixture, Scene, SceneAssignment, SceneCreate, SceneUpdate } from "../../types";

interface AssignmentDraft {
  key: string;
  effect_id: number | "";
  target: "all" | "specific";
  fixture_ids: number[];
  brightness: number;
}

let draftKeySeq = 0;
function nextDraftKey(): string {
  draftKeySeq += 1;
  return `draft-${draftKeySeq}`;
}

function assignmentToDraft(a: SceneAssignment): AssignmentDraft {
  return {
    key: nextDraftKey(),
    effect_id: a.effect_id,
    target: a.fixture_ids === "all" ? "all" : "specific",
    fixture_ids: a.fixture_ids === "all" ? [] : a.fixture_ids,
    brightness: a.brightness,
  };
}

interface SceneEditorProps {
  scene: Scene | null;
  effects: Effect[];
  fixtures: Fixture[];
  onSave: (payload: SceneCreate | SceneUpdate) => Promise<void>;
  onCancel: () => void;
  onDelete?: (id: number) => void;
}

export function SceneEditor({ scene, effects, fixtures, onSave, onCancel, onDelete }: SceneEditorProps) {
  const [name, setName] = useState(scene?.name ?? "");
  const [assignments, setAssignments] = useState<AssignmentDraft[]>(
    scene ? scene.assignments.map(assignmentToDraft) : [],
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function addAssignment() {
    setAssignments((prev) => [
      ...prev,
      { key: nextDraftKey(), effect_id: effects[0]?.id ?? "", target: "all", fixture_ids: [], brightness: 1 },
    ]);
  }

  function removeAssignment(key: string) {
    setAssignments((prev) => prev.filter((a) => a.key !== key));
  }

  function updateAssignment(key: string, patch: Partial<AssignmentDraft>) {
    setAssignments((prev) => prev.map((a) => (a.key === key ? { ...a, ...patch } : a)));
  }

  function toggleFixture(key: string, fixtureId: number) {
    setAssignments((prev) =>
      prev.map((a) => {
        if (a.key !== key) return a;
        const has = a.fixture_ids.includes(fixtureId);
        return {
          ...a,
          fixture_ids: has ? a.fixture_ids.filter((id) => id !== fixtureId) : [...a.fixture_ids, fixtureId],
        };
      }),
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (assignments.length === 0) {
      setError("Add at least one assignment.");
      return;
    }
    for (const a of assignments) {
      if (a.effect_id === "") {
        setError("Every assignment needs an effect.");
        return;
      }
      if (a.target === "specific" && a.fixture_ids.length === 0) {
        setError('Pick at least one fixture, or switch to "All fixtures".');
        return;
      }
    }

    const payloadAssignments: SceneAssignment[] = assignments.map((a) => ({
      effect_id: a.effect_id as number,
      fixture_ids: a.target === "all" ? "all" : a.fixture_ids,
      params: {},
      brightness: a.brightness,
    }));

    setSaving(true);
    try {
      await onSave({ name: name.trim(), assignments: payloadAssignments });
    } catch {
      setError("Failed to save scene.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="scene-editor" onSubmit={(e) => void submit(e)}>
      <div className="scene-editor__head">
        <h2>{scene ? "Edit scene" : "New scene"}</h2>
        <button type="button" className="btn btn--small btn--icon" onClick={onCancel}>
          Close
        </button>
      </div>

      <input type="text" placeholder="Scene name" value={name} onChange={(e) => setName(e.target.value)} />

      {assignments.map((a) => (
        <div key={a.key} className="scene-editor__assignment">
          <div className="scene-editor__assignment-head">
            <select
              value={a.effect_id}
              onChange={(e) => updateAssignment(a.key, { effect_id: e.target.value ? Number(e.target.value) : "" })}
            >
              <option value="">Select effect…</option>
              {effects.map((effect) => (
                <option key={effect.id} value={effect.id}>
                  {effect.name}
                </option>
              ))}
            </select>
            <button type="button" className="btn btn--small btn--danger" onClick={() => removeAssignment(a.key)}>
              Remove
            </button>
          </div>

          <div className="scene-editor__target-row">
            <label className="scene-editor__target">
              <input
                type="radio"
                name={`target-${a.key}`}
                checked={a.target === "all"}
                onChange={() => updateAssignment(a.key, { target: "all" })}
              />
              All fixtures
            </label>
            <label className="scene-editor__target">
              <input
                type="radio"
                name={`target-${a.key}`}
                checked={a.target === "specific"}
                onChange={() => updateAssignment(a.key, { target: "specific" })}
              />
              Specific fixtures
            </label>
          </div>

          {a.target === "specific" && (
            <div className="scene-editor__fixtures">
              {fixtures.length === 0 && <span className="scene-editor__empty">No fixtures in project.</span>}
              {fixtures.map((f) => {
                const selected = a.fixture_ids.includes(f.id);
                return (
                  <button
                    type="button"
                    key={f.id}
                    className={`scene-editor__fixture-chip ${selected ? "scene-editor__fixture-chip--selected" : ""}`}
                    onClick={() => toggleFixture(a.key, f.id)}
                  >
                    {f.name}
                  </button>
                );
              })}
            </div>
          )}

          <label className="scene-editor__brightness">
            Brightness
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={a.brightness}
              onChange={(e) => updateAssignment(a.key, { brightness: Number(e.target.value) })}
            />
            <span>{Math.round(a.brightness * 100)}%</span>
          </label>
        </div>
      ))}

      <button type="button" className="btn btn--small" onClick={addAssignment} disabled={effects.length === 0}>
        + Add assignment
      </button>
      {effects.length === 0 && (
        <p className="scene-editor__empty">No effects yet — build one in the effect editor first.</p>
      )}

      {error && <p className="banner banner--error">{error}</p>}

      <div className="scene-editor__actions">
        <div>
          {scene && onDelete && (
            <button type="button" className="btn btn--danger" onClick={() => onDelete(scene.id)}>
              Delete scene
            </button>
          )}
        </div>
        <div className="scene-editor__actions-right">
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn btn--accent" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </form>
  );
}
