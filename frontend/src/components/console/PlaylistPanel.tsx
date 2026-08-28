import { useCallback, useEffect, useMemo, useState } from "react";
import { useLiveMessage } from "../../api/useLiveSocket";
import { playlistsApi } from "../../api/resources";
import { useSceneStore } from "../../store/useSceneStore";
import type {
  PhraseClockState,
  Playlist,
  PlaylistAdvanceTrigger,
  PlaylistMode,
  PlaylistStatus,
  PlaylistUpdate,
} from "../../types";
import "./playlist.css";

const MODES: PlaylistMode[] = ["sequential", "shuffle", "pingpong"];
const TRIGGERS: PlaylistAdvanceTrigger[] = [
  "beats",
  "bars",
  "tempo_change",
  "time",
  "hype",
  "manual",
];

interface Draft {
  name: string;
  entries: number[]; // scene ids, in order
  mode: PlaylistMode;
  advance_trigger: PlaylistAdvanceTrigger;
  advance_beats: number;
  advance_seconds: number;
  hype_threshold: number;
}

function toDraft(p: Playlist): Draft {
  return {
    name: p.name,
    entries: p.entries.map((e) => e.scene_id),
    mode: p.mode,
    advance_trigger: p.advance_trigger,
    advance_beats: p.advance_beats,
    advance_seconds: p.advance_seconds,
    hype_threshold: p.hype_threshold,
  };
}

export function PlaylistPanel() {
  const scenes = useSceneStore((s) => s.scenes);
  const sceneName = useCallback(
    (id: number | null) => (id == null ? "—" : scenes.find((s) => s.id === id)?.name ?? `#${id}`),
    [scenes],
  );

  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [status, setStatus] = useState<PlaylistStatus | null>(null);
  const [phrase, setPhrase] = useState<PhraseClockState | null>(null);

  const refresh = useCallback(async () => {
    const list = await playlistsApi.list();
    setPlaylists(list);
    setSelectedId((cur) => cur ?? list.find((p) => p.active)?.id ?? list[0]?.id ?? null);
  }, []);

  useEffect(() => {
    void refresh();
    void playlistsApi.status().then(setStatus).catch(() => undefined);
  }, [refresh]);

  const selected = useMemo(
    () => playlists.find((p) => p.id === selectedId) ?? null,
    [playlists, selectedId],
  );

  useEffect(() => {
    setDraft(selected ? toDraft(selected) : null);
    setError(null);
  }, [selected]);

  const onPlaylist = useCallback((m: Record<string, unknown>) => {
    setStatus({
      playlist_id: (m.playlist_id as number | null) ?? null,
      index: typeof m.index === "number" ? m.index : 0,
      scene_id: (m.scene_id as number | null) ?? null,
      next_scene_id: (m.next_scene_id as number | null) ?? null,
      beats_until_advance: (m.beats_until_advance as number | null) ?? null,
      seconds_until_advance: (m.seconds_until_advance as number | null) ?? null,
    });
  }, []);
  const onPhrase = useCallback((m: Record<string, unknown>) => {
    setPhrase({
      bpm: Number(m.bpm ?? 0),
      total_beats: Number(m.total_beats ?? 0),
      phrase_beat: Number(m.phrase_beat ?? 0),
      phrase_index: Number(m.phrase_index ?? 0),
      phrase_beats: Number(m.phrase_beats ?? 0),
      bar: Number(m.bar ?? 0),
      phrase_phase: Number(m.phrase_phase ?? 0),
    });
  }, []);
  useLiveMessage("playlist", onPlaylist);
  useLiveMessage("phrase", onPhrase);

  function patchDraft(patch: Partial<Draft>) {
    setDraft((d) => (d ? { ...d, ...patch } : d));
  }

  function moveEntry(i: number, dir: -1 | 1) {
    setDraft((d) => {
      if (!d) return d;
      const j = i + dir;
      if (j < 0 || j >= d.entries.length) return d;
      const entries = [...d.entries];
      [entries[i], entries[j]] = [entries[j], entries[i]];
      return { ...d, entries };
    });
  }

  async function withBusy(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch {
      setError("Request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createPlaylist() {
    await withBusy(async () => {
      const created = await playlistsApi.create({ name: "New playlist", entries: [] });
      await refresh();
      setSelectedId(created.id);
    });
  }

  async function save() {
    if (!draft || !selected) return;
    const payload: PlaylistUpdate = {
      name: draft.name.trim() || "Untitled",
      entries: draft.entries.map((scene_id) => ({ scene_id })),
      mode: draft.mode,
      advance_trigger: draft.advance_trigger,
      advance_beats: draft.advance_beats,
      advance_seconds: draft.advance_seconds,
      hype_threshold: draft.hype_threshold,
    };
    await withBusy(async () => {
      await playlistsApi.update(selected.id, payload);
      await refresh();
    });
  }

  async function remove() {
    if (!selected) return;
    await withBusy(async () => {
      await playlistsApi.remove(selected.id);
      setSelectedId(null);
      await refresh();
    });
  }

  async function activate() {
    if (!selected) return;
    await withBusy(async () => {
      await playlistsApi.activate(selected.id);
      await refresh();
    });
  }

  async function deactivate() {
    await withBusy(async () => {
      await playlistsApi.deactivate();
      await refresh();
      setStatus(null);
    });
  }

  async function step(dir: -1 | 1) {
    if (!selected) return;
    await withBusy(async () => {
      const st = dir === 1 ? await playlistsApi.next(selected.id) : await playlistsApi.prev(selected.id);
      setStatus(st);
    });
  }

  const trigger = draft?.advance_trigger;
  const activeId = playlists.find((p) => p.active)?.id ?? null;

  return (
    <div className="playlist-panel">
      <div className="playlist-panel__head">
        <h2>Playlists</h2>
        <button className="btn btn--small" onClick={() => void createPlaylist()} disabled={busy}>
          + New
        </button>
      </div>

      <div className="playlist-panel__status">
        {status?.playlist_id != null ? (
          <>
            <span className="playlist-panel__now">▶ {sceneName(status.scene_id)}</span>
            <span className="playlist-panel__next">next: {sceneName(status.next_scene_id)}</span>
            <span className="playlist-panel__until">
              {status.beats_until_advance != null
                ? `${status.beats_until_advance} beats until next`
                : status.seconds_until_advance != null
                  ? `${status.seconds_until_advance.toFixed(1)}s until next`
                  : "manual advance"}
            </span>
          </>
        ) : (
          <span className="playlist-panel__idle">No playlist running</span>
        )}
        <span className="playlist-panel__phrase">
          {phrase ? `${Math.round(phrase.bpm)} BPM · beat ${phrase.phrase_beat + 1} of ${phrase.phrase_beats}` : "— BPM"}
        </span>
      </div>

      {playlists.length === 0 ? (
        <p className="playlist-panel__empty">No playlists yet. Create one to auto-advance scenes on the beat.</p>
      ) : (
        <ul className="playlist-panel__list">
          {playlists.map((p) => (
            <li key={p.id} className={`playlist-row ${p.id === selectedId ? "playlist-row--sel" : ""}`}>
              <button className="playlist-row__pick" onClick={() => setSelectedId(p.id)}>
                <span className={`playlist-row__dot ${p.id === activeId ? "playlist-row__dot--live" : ""}`} />
                <span className="playlist-row__name">{p.name}</span>
                <span className="playlist-row__meta">{p.entries.length} · {p.advance_trigger}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {draft && selected && (
        <div className="playlist-editor">
          <input
            className="playlist-editor__name"
            type="text"
            value={draft.name}
            onChange={(e) => patchDraft({ name: e.target.value })}
            placeholder="Playlist name"
          />

          <div className="playlist-editor__entries">
            {draft.entries.length === 0 && <p className="playlist-panel__empty">No entries. Add a scene below.</p>}
            {draft.entries.map((sceneId, i) => (
              <div key={i} className="playlist-entry">
                <span className="playlist-entry__idx">{i + 1}</span>
                <select
                  value={sceneId}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    patchDraft({ entries: draft.entries.map((s, k) => (k === i ? id : s)) });
                  }}
                >
                  {scenes.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button className="btn btn--small btn--icon" onClick={() => moveEntry(i, -1)} disabled={i === 0}>
                  ↑
                </button>
                <button
                  className="btn btn--small btn--icon"
                  onClick={() => moveEntry(i, 1)}
                  disabled={i === draft.entries.length - 1}
                >
                  ↓
                </button>
                <button
                  className="btn btn--small btn--danger"
                  onClick={() => patchDraft({ entries: draft.entries.filter((_, k) => k !== i) })}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              className="btn btn--small"
              disabled={scenes.length === 0}
              onClick={() => patchDraft({ entries: [...draft.entries, scenes[0]?.id ?? 0] })}
            >
              + Add entry
            </button>
          </div>

          <div className="playlist-editor__row">
            <label>
              Mode
              <select value={draft.mode} onChange={(e) => patchDraft({ mode: e.target.value as PlaylistMode })}>
                {MODES.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Advance on
              <select
                value={draft.advance_trigger}
                onChange={(e) => patchDraft({ advance_trigger: e.target.value as PlaylistAdvanceTrigger })}
              >
                {TRIGGERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            {(trigger === "beats" || trigger === "bars") && (
              <label>
                Every N {trigger}
                <input
                  type="number"
                  min={1}
                  value={draft.advance_beats}
                  onChange={(e) => patchDraft({ advance_beats: Math.max(1, Number(e.target.value)) })}
                />
              </label>
            )}
            {trigger === "time" && (
              <label>
                Seconds
                <input
                  type="number"
                  min={0.1}
                  step={0.5}
                  value={draft.advance_seconds}
                  onChange={(e) => patchDraft({ advance_seconds: Math.max(0.1, Number(e.target.value)) })}
                />
              </label>
            )}
            {trigger === "hype" && (
              <label>
                Hype threshold
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={draft.hype_threshold}
                  onChange={(e) => patchDraft({ hype_threshold: Number(e.target.value) })}
                />
              </label>
            )}
          </div>

          {error && <p className="banner banner--error">{error}</p>}

          <div className="playlist-editor__actions">
            <div className="playlist-editor__transport">
              <button className="btn btn--small" onClick={() => void step(-1)} disabled={busy || !selected.active}>
                ◀ Prev
              </button>
              <button className="btn btn--small" onClick={() => void step(1)} disabled={busy || !selected.active}>
                Next ▶
              </button>
            </div>
            <div className="playlist-editor__actions-right">
              {selected.active ? (
                <button className="btn btn--small" onClick={() => void deactivate()} disabled={busy}>
                  Deactivate
                </button>
              ) : (
                <button className="btn btn--small btn--accent" onClick={() => void activate()} disabled={busy}>
                  Activate
                </button>
              )}
              <button className="btn btn--small btn--danger" onClick={() => void remove()} disabled={busy}>
                Delete
              </button>
              <button className="btn btn--accent" onClick={() => void save()} disabled={busy}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
