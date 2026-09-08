import { useEffect, useMemo, useState } from "react";
import { useFixtureStore } from "../store/useFixtureStore";
import { useDeviceStore } from "../store/useDeviceStore";
import { SceneViewer } from "../components/3d/SceneViewer";
import { Knob } from "../components/controls/Knob";
import { SegMeter } from "../components/controls/SegMeter";
import { polylineLength } from "../utils/polyline";
import type { Fixture, FixtureCreate, Point3 } from "../types";
import "./BuilderPage.css";

interface Draft {
  name: string;
  device_id: number | "";
  led_count: number;
  start_channel: number;
  points: Point3[];
  reverse: boolean;
}

function fixtureToDraft(f: Fixture): Draft {
  return {
    name: f.name,
    device_id: f.device_id,
    led_count: f.led_count,
    start_channel: f.start_channel,
    points: f.points.map((p) => [...p] as Point3),
    reverse: f.reverse,
  };
}

function emptyDraft(deviceId: number | "", startChannel: number): Draft {
  return {
    name: "",
    device_id: deviceId,
    led_count: 30,
    start_channel: startChannel,
    points: [
      [0, 0, 0],
      [1, 0, 0],
    ],
    reverse: false,
  };
}

/** One physical WLED device's pixel buffer can be carved into several fixtures
 * (e.g. a strip that runs along three walls) by giving each a non-overlapping
 * start_channel/led_count slice. This sums up what's already claimed on a
 * device so the editor can suggest where the next segment should start. */
function nextAvailableChannel(fixtures: Fixture[], deviceId: number, excludeFixtureId: number | null): number {
  return fixtures
    .filter((f) => f.device_id === deviceId && f.id !== excludeFixtureId)
    .reduce((max, f) => Math.max(max, f.start_channel + f.led_count), 0);
}

/** Fixture ids whose channel range overlaps another fixture on the same device --
 * they'll fight over the same pixels at render time and one will silently clobber
 * the other's output. */
function findChannelConflicts(fixtures: Fixture[]): Set<number> {
  const conflicts = new Set<number>();
  const byDevice = new Map<number, Fixture[]>();
  for (const f of fixtures) {
    if (!byDevice.has(f.device_id)) byDevice.set(f.device_id, []);
    byDevice.get(f.device_id)!.push(f);
  }
  for (const group of byDevice.values()) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i];
        const b = group[j];
        const overlaps = a.start_channel < b.start_channel + b.led_count && b.start_channel < a.start_channel + a.led_count;
        if (overlaps) {
          conflicts.add(a.id);
          conflicts.add(b.id);
        }
      }
    }
  }
  return conflicts;
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
    // Deliberately no default device: silently defaulting to the first device
    // in the list caused fixtures to get saved against the wrong device
    // whenever the user forgot to touch the dropdown. Forcing an explicit
    // pick (the select's blank placeholder) is the only way to catch that.
    setDraft(emptyDraft("", 0));
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
      reverse: draft.reverse,
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

  const devicesById = useMemo(() => new Map(devices.map((d) => [d.id, d])), [devices]);
  const channelConflicts = useMemo(() => findChannelConflicts(fixtures), [fixtures]);

  const draftDevice = draft && draft.device_id !== "" ? devices.find((d) => d.id === draft.device_id) : undefined;
  const siblingFixtures =
    draft && draft.device_id !== "" ? fixtures.filter((f) => f.device_id === draft.device_id && f.id !== selectedId) : [];
  const suggestedStartChannel =
    draft && draft.device_id !== "" ? nextAvailableChannel(fixtures, draft.device_id, selectedId) : 0;
  const draftEndChannel = draft ? draft.start_channel + draft.led_count : 0;
  const draftOverflowsDevice = draftDevice ? draftEndChannel > draftDevice.led_count : false;

  return (
    <div className="builder-page">
      <div className="builder-page__viewport">
        <SceneViewer fixtures={fixtures} selectedId={selectedId} onSelect={selectFixture} />
      </div>
      <aside className="builder-page__panel">
        <div className="builder-panel__header">
          <span className="section-label">Fixtures</span>
          <button className="btn btn--small" onClick={startNewFixture}>
            New fixture
          </button>
        </div>

        <ul className="fixture-list">
          {fixtures.map((f) => {
            const deviceName = devicesById.get(f.device_id)?.name;
            const hasConflict = channelConflicts.has(f.id);
            return (
              <li key={f.id}>
                <button
                  className={`fixture-list__item ${f.id === selectedId ? "fixture-list__item--active" : ""} ${hasConflict ? "fixture-list__item--conflict" : ""}`}
                  onClick={() => selectFixture(f.id)}
                >
                  <span>{f.name}</span>
                  <span className="fixture-list__meta">
                    {f.led_count} LEDs · {deviceName ?? "⚠ unknown device"}
                    {hasConflict && " · ⚠ channel conflict"}
                  </span>
                </button>
              </li>
            );
          })}
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

            <div className="fixture-editor__row fixture-editor__row--controls">
              <Knob
                label="LED count"
                value={draft.led_count}
                min={1}
                max={300}
                step={1}
                accent="cyan"
                onChange={(v) => updateDraft({ led_count: v })}
              />
              <label className="fixture-editor__num">
                Start channel
                <input
                  type="number"
                  min={0}
                  value={draft.start_channel}
                  onChange={(e) => updateDraft({ start_channel: Number(e.target.value) })}
                />
              </label>
            </div>

            {draftDevice && (
              <div className="fixture-editor__fill">
                <div className="fixture-editor__fill-head">
                  <span>Device fill</span>
                  <span>
                    {draftEndChannel} / {draftDevice.led_count}
                  </span>
                </div>
                <SegMeter
                  value={draftDevice.led_count ? draftEndChannel / draftDevice.led_count : 0}
                  segments={20}
                />
              </div>
            )}

            {draft.device_id !== "" && (
              <div className="fixture-editor__channel-hint">
                <span>
                  {siblingFixtures.length > 0
                    ? `${siblingFixtures.length} other fixture${siblingFixtures.length === 1 ? "" : "s"} on this device use channels up to ${suggestedStartChannel - 1}.`
                    : "This is the only fixture on this device so far."}
                </span>
                {draft.start_channel !== suggestedStartChannel && (
                  <button
                    type="button"
                    className="btn btn--small"
                    onClick={() => updateDraft({ start_channel: suggestedStartChannel })}
                  >
                    Use next available ({suggestedStartChannel})
                  </button>
                )}
                {draftOverflowsDevice && (
                  <span className="fixture-editor__channel-warning">
                    ⚠ channels {draft.start_channel}–{draftEndChannel - 1} exceed this device's {draftDevice?.led_count}{" "}
                    LEDs
                  </span>
                )}
              </div>
            )}

            <div className="fixture-editor__points">
              <div className="fixture-editor__points-header">
                <span>Path points</span>
                <span className="fixture-editor__length">{draftLength.toFixed(2)} m</span>
              </div>
              <label className="fixture-editor__reverse">
                <input
                  type="checkbox"
                  checked={draft.reverse}
                  onChange={(e) => updateDraft({ reverse: e.target.checked })}
                />
                Reverse — LED 1 is at the {draft.reverse ? "last" : "first"} point below
              </label>
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
