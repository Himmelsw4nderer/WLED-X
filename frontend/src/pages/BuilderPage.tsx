import { useEffect, useMemo, useState } from "react";
import { useFixtureStore } from "../store/useFixtureStore";
import { useDeviceStore } from "../store/useDeviceStore";
import { SceneViewer } from "../components/3d/SceneViewer";
import { polylineLength } from "../utils/polyline";
import type { Fixture, FixtureCreate, Point3 } from "../types";
import "./BuilderPage.css";

interface Draft {
  name: string;
  device_id: number | "";
  led_count: number;
  start_channel: number;
  points: Point3[];
}

function fixtureToDraft(f: Fixture): Draft {
  return {
    name: f.name,
    device_id: f.device_id,
    led_count: f.led_count,
    start_channel: f.start_channel,
    points: f.points.map((p) => [...p] as Point3),
  };
}

function emptyDraft(deviceId: number | ""): Draft {
  return {
    name: "",
    device_id: deviceId,
    led_count: 30,
    start_channel: 0,
    points: [
      [0, 0, 0],
      [1, 0, 0],
    ],
  };
}

export function BuilderPage() {
  const { fixtures, refresh: refreshFixtures, add, update, remove } = useFixtureStore();
  const { devices, refresh: refreshDevices } = useDeviceStore();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshFixtures();
    void refreshDevices();
  }, [refreshFixtures, refreshDevices]);

  const selectedFixture = useMemo(
    () => fixtures.find((f) => f.id === selectedId) ?? null,
    [fixtures, selectedId],
  );

  function selectFixture(id: number | null) {
    setSelectedId(id);
    setError(null);
    if (id === null) {
      setDraft(null);
      return;
    }
    const f = fixtures.find((x) => x.id === id);
    setDraft(f ? fixtureToDraft(f) : null);
  }

  function startNewFixture() {
    setSelectedId(null);
    setError(null);
    setDraft(emptyDraft(devices[0]?.id ?? ""));
  }

  function updateDraft(patch: Partial<Draft>) {
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev));
  }

  function updatePoint(index: number, axis: 0 | 1 | 2, value: number) {
    if (!draft || Number.isNaN(value)) return;
    const points = draft.points.map((p) => [...p] as Point3);
    points[index][axis] = value;
    updateDraft({ points });
  }

  function addPoint() {
    if (!draft) return;
    const last = draft.points[draft.points.length - 1] ?? [0, 0, 0];
    updateDraft({ points: [...draft.points, [last[0] + 1, last[1], last[2]]] });
  }

  function removePoint(index: number) {
    if (!draft || draft.points.length <= 2) return;
    updateDraft({ points: draft.points.filter((_, i) => i !== index) });
  }

  async function saveDraft() {
    if (!draft) return;
    if (!draft.name.trim()) {
      setError("Name is required.");
      return;
    }
    if (draft.device_id === "") {
      setError("Select a device.");
      return;
    }
    const payload: FixtureCreate = {
      name: draft.name.trim(),
      device_id: draft.device_id,
      led_count: draft.led_count,
      start_channel: draft.start_channel,
      points: draft.points,
    };
    setSaving(true);
    setError(null);
    try {
      if (selectedId !== null) {
        await update(selectedId, payload);
      } else {
        const created = await add(payload);
        setSelectedId(created.id);
      }
    } catch {
      setError("Failed to save fixture.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSelected() {
    if (selectedId === null) return;
    setSaving(true);
    setError(null);
    try {
      await remove(selectedId);
      setSelectedId(null);
      setDraft(null);
    } catch {
      setError("Failed to delete fixture.");
    } finally {
      setSaving(false);
    }
  }

  const draftLength = draft ? polylineLength(draft.points) : 0;

  return (
    <div className="builder-page">
      <div className="builder-page__viewport">
        <SceneViewer fixtures={fixtures} selectedId={selectedId} onSelect={selectFixture} />
      </div>
      <aside className="builder-page__panel">
        <div className="builder-panel__header">
          <h2>Fixtures</h2>
          <button className="btn btn--small" onClick={startNewFixture}>
            New fixture
          </button>
        </div>

        <ul className="fixture-list">
          {fixtures.map((f) => (
            <li key={f.id}>
              <button
                className={`fixture-list__item ${f.id === selectedId ? "fixture-list__item--active" : ""}`}
                onClick={() => selectFixture(f.id)}
              >
                <span>{f.name}</span>
                <span className="fixture-list__meta">{f.led_count} LEDs</span>
              </button>
            </li>
          ))}
          {fixtures.length === 0 && <li className="fixture-list__empty">No fixtures yet.</li>}
        </ul>

        {draft && (
          <div className="fixture-editor">
            <label>
              Name
              <input value={draft.name} onChange={(e) => updateDraft({ name: e.target.value })} />
            </label>

            <label>
              Device
              <select
                value={draft.device_id}
                onChange={(e) => updateDraft({ device_id: e.target.value ? Number(e.target.value) : "" })}
              >
                <option value="">Select a device…</option>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="fixture-editor__row">
              <label>
                LED count
                <input
                  type="number"
                  min={1}
                  value={draft.led_count}
                  onChange={(e) => updateDraft({ led_count: Number(e.target.value) })}
                />
              </label>
              <label>
                Start channel
                <input
                  type="number"
                  min={0}
                  value={draft.start_channel}
                  onChange={(e) => updateDraft({ start_channel: Number(e.target.value) })}
                />
              </label>
            </div>

            <div className="fixture-editor__points">
              <div className="fixture-editor__points-header">
                <span>Path points</span>
                <span className="fixture-editor__length">{draftLength.toFixed(2)} m</span>
              </div>
              {draft.points.map((p, i) => (
                <div className="point-row" key={i}>
                  <span className="point-row__index">{i + 1}</span>
                  {([0, 1, 2] as const).map((axis) => (
                    <input
                      key={axis}
                      type="number"
                      step={0.1}
                      value={p[axis]}
                      onChange={(e) => updatePoint(i, axis, Number(e.target.value))}
                    />
                  ))}
                  <button
                    className="btn btn--icon"
                    onClick={() => removePoint(i)}
                    disabled={draft.points.length <= 2}
                    title="Remove point"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button className="btn btn--small" onClick={addPoint}>
                Add point
              </button>
            </div>

            {error && <p className="banner banner--error">{error}</p>}

            <div className="fixture-editor__actions">
              <button className="btn btn--accent" onClick={() => void saveDraft()} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
              {selectedFixture && (
                <button className="btn btn--danger" onClick={() => void deleteSelected()} disabled={saving}>
                  Delete
                </button>
              )}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
