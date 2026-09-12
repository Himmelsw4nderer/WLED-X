import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleStore } from "../store/useConsoleStore";
import { useSceneStore } from "../store/useSceneStore";
import { useEffectStore } from "../store/useEffectStore";
import { useFixtureStore } from "../store/useFixtureStore";
import { SceneTransport } from "../components/console/SceneTransport";
import { SceneEditor } from "../components/console/SceneEditor";
import { ColorSchemeSelect } from "../components/console/ColorSchemeSelect";
import { ConsoleCard } from "../components/console/ConsoleCard";
import { MasterFader } from "../components/console/MasterFader";
import { ParamFader } from "../components/console/ParamFader";
import { ParamSelect } from "../components/console/ParamSelect";
import { HitButton } from "../components/console/HitButton";
import { GlobalSourceSelect } from "../components/console/GlobalSourceSelect";
import { AudioMeter } from "../components/console/AudioMeter";
import { AudioSourcePicker } from "../components/console/AudioSourcePicker";
import { PlaylistPanel } from "../components/console/PlaylistPanel";
import { playlistsApi } from "../api/resources";
import type { ControlAccent } from "../components/controls/Fader";
import type { Effect, Scene, SceneCreate, SceneUpdate } from "../types";
import "../components/console/console.css";

type EditorState = { mode: "create" } | { mode: "edit"; scene: Scene };

// One fader-group card per effect gets its own accent from the house palette
// instead of every channel reading the same cyan -- cycling by position keeps
// it deterministic (the same effect always lands on the same color) without
// needing to track per-effect state.
const FADER_GROUP_ACCENTS: ControlAccent[] = ["cyan", "lime", "gold", "violet", "ember", "accent"];

export function ConsolePage() {
  const connect = useConsoleStore((s) => s.connect);
  const masterBrightness = useConsoleStore((s) => s.master_brightness);
  const setMasterBrightness = useConsoleStore((s) => s.setMasterBrightness);
  const consoleActiveSceneId = useConsoleStore((s) => s.active_scene_id);
  const setActiveScene = useConsoleStore((s) => s.setActiveScene);
  const paramOverrides = useConsoleStore((s) => s.param_overrides);
  const setParamOverride = useConsoleStore((s) => s.setParamOverride);

  const scenes = useSceneStore((s) => s.scenes);
  const scenesLoading = useSceneStore((s) => s.loading);
  const refreshScenes = useSceneStore((s) => s.refresh);
  const addScene = useSceneStore((s) => s.add);
  const updateScene = useSceneStore((s) => s.update);
  const removeScene = useSceneStore((s) => s.remove);
  const activateScene = useSceneStore((s) => s.activate);

  const effects = useEffectStore((s) => s.effects);
  const refreshEffects = useEffectStore((s) => s.refresh);

  const fixtures = useFixtureStore((s) => s.fixtures);
  const refreshFixtures = useFixtureStore((s) => s.refresh);

  const [editorState, setEditorState] = useState<EditorState | null>(null);

  useEffect(() => {
    connect();
    void refreshScenes();
    void refreshEffects();
    void refreshFixtures();
  }, [connect, refreshScenes, refreshEffects, refreshFixtures]);

  // Manual playlist transport: "[" = prev entry, "]" = next entry on the
  // active playlist (mirrors the Prev/Next buttons in PlaylistPanel).
  useEffect(() => {
    async function handle(e: KeyboardEvent) {
      if (e.key !== "[" && e.key !== "]") return;
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      const active = (await playlistsApi.list()).find((p) => p.active);
      if (!active) return;
      await (e.key === "]" ? playlistsApi.next(active.id) : playlistsApi.prev(active.id));
    }
    const onKey = (e: KeyboardEvent) => void handle(e);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // The render loop reads `Scene.active` from the DB each tick, not
  // console_state.active_scene_id (see effects/engine.py _tick_once) -- the
  // DB row is the source of truth for what's actually live. We fall back to
  // the console's copy only for the instant after a click, before refresh()
  // has landed.
  const dbActiveScene = scenes.find((s) => s.active) ?? null;
  const activeScene = dbActiveScene ?? scenes.find((s) => s.id === consoleActiveSceneId) ?? null;
  const activeSceneId = activeScene?.id ?? null;

  async function selectScene(scene: Scene) {
    setActiveScene(scene.id);
    await activateScene(scene.id);
  }

  async function saveScene(payload: SceneCreate | SceneUpdate, existing: Scene | null) {
    if (existing) {
      await updateScene(existing.id, payload as SceneUpdate);
    } else {
      await addScene(payload as SceneCreate);
    }
    setEditorState(null);
  }

  async function deleteScene(id: number) {
    await removeScene(id);
    setEditorState(null);
  }

  const effectsById = useMemo(() => new Map(effects.map((e) => [e.id, e])), [effects]);

  const liveEffects = useMemo(() => {
    if (!activeScene) return [];
    const seen = new Set<number>();
    const result: Effect[] = [];
    for (const assignment of activeScene.assignments) {
      if (seen.has(assignment.effect_id)) continue;
      const effect = effectsById.get(assignment.effect_id);
      if (!effect) continue;
      seen.add(assignment.effect_id);
      result.push(effect);
    }
    return result;
  }, [activeScene, effectsById]);

  const totalParams = liveEffects.reduce((n, e) => n + e.exposed_params.length, 0);

  // --- Fader bank <-> scene persistence -----------------------------------
  // Riding a fader pushes a live console override for instant feedback (see
  // setParamOverride) AND, debounced, writes the value onto the active
  // scene's assignments so it survives a scene switch or reload. The effect
  // only defines which params are exposed; their live values live on the
  // scene, keyed "{node_id}:{param_key}" per effect.
  const pendingParamsRef = useRef(new Map<number, Record<string, number | string>>());
  const flushSceneIdRef = useRef<number | null>(null);
  const flushTimerRef = useRef<number | null>(null);

  const flushSceneParams = useCallback(() => {
    flushTimerRef.current = null;
    const pending = pendingParamsRef.current;
    pendingParamsRef.current = new Map();
    const scene = scenes.find((s) => s.id === flushSceneIdRef.current);
    if (!scene || pending.size === 0) return;
    const assignments = scene.assignments.map((a) => {
      const patch = pending.get(a.effect_id);
      return patch ? { ...a, params: { ...a.params, ...patch } } : a;
    });
    void updateScene(scene.id, { assignments });
  }, [scenes, updateScene]);

  const persistSceneParam = useCallback(
    (effectId: number, nodeId: string, paramKey: string, value: number | string) => {
      if (activeSceneId == null) return;
      flushSceneIdRef.current = activeSceneId;
      const patch = pendingParamsRef.current.get(effectId) ?? {};
      patch[`${nodeId}:${paramKey}`] = value;
      pendingParamsRef.current.set(effectId, patch);
      if (flushTimerRef.current !== null) window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = window.setTimeout(flushSceneParams, 500);
    },
    [activeSceneId, flushSceneParams],
  );

  useEffect(
    () => () => {
      if (flushTimerRef.current !== null) window.clearTimeout(flushTimerRef.current);
    },
    [],
  );

  const sceneParamValue = useCallback(
    (effectId: number, nodeId: string, paramKey: string): number | string | undefined => {
      const key = `${nodeId}:${paramKey}`;
      for (const a of activeScene?.assignments ?? []) {
        if (a.effect_id === effectId && a.params?.[key] !== undefined) return a.params[key];
      }
      return undefined;
    },
    [activeScene],
  );

  return (
    <div className="page console-page">
      <div className="console-deck">
        <ConsoleCard title="Master" accent="accent" className="console-deck__master">
          <MasterFader value={masterBrightness} onChange={setMasterBrightness} />
          <HitButton />
          <ColorSchemeSelect />
        </ConsoleCard>

        <ConsoleCard
          title="Scenes"
          accent="gold"
          className="console-deck__cues"
          actions={
            <button className="btn btn--small" onClick={() => setEditorState({ mode: "create" })}>
              + New scene
            </button>
          }
        >
          <SceneTransport
            scenes={scenes}
            loading={scenesLoading}
            activeSceneId={activeSceneId}
            onSelect={(scene) => void selectScene(scene)}
            onEdit={(scene) => setEditorState({ mode: "edit", scene })}
          />
        </ConsoleCard>

        <ConsoleCard title="Audio" accent="cyan" className="console-deck__audio">
          <AudioMeter />
          <div className="console-deck__audio-io">
            <GlobalSourceSelect />
            <AudioSourcePicker />
          </div>
        </ConsoleCard>
      </div>

      <div className="console-lower">
        <ConsoleCard
          title="Fader Bank"
          accent="gold"
          className="console-page__rack"
          actions={
            <span>
              {activeScene ? activeScene.name : "no scene live"}
              {totalParams > 0 && ` · ${totalParams} channel${totalParams === 1 ? "" : "s"}`}
            </span>
          }
        >
          <div className="console-page__faders">
            {!activeScene && (
              <p className="console-page__hint">No scene is live. Pick one on the left to start riding faders.</p>
            )}
            {activeScene && liveEffects.length === 0 && (
              <p className="console-page__hint">This scene has no effect assignments yet — edit it to add some.</p>
            )}
            {liveEffects.map((effect, effectIndex) => {
              const accent = FADER_GROUP_ACCENTS[effectIndex % FADER_GROUP_ACCENTS.length];
              const selectParams = effect.exposed_params.filter((p) => p.options && p.options.length > 0);
              const faderParams = effect.exposed_params.filter((p) => !p.options || p.options.length === 0);

              return (
                <ConsoleCard key={effect.id} title={effect.name} accent={accent} className="fader-group">
                  {selectParams.length > 0 && (
                    <div className="fader-group__selects">
                      {selectParams.map((param) => {
                        const key = `${effect.id}:${param.node_id}:${param.param_key}`;
                        const override = paramOverrides[key];
                        const sceneVal = sceneParamValue(effect.id, param.node_id, param.param_key);
                        const ride = (v: number | string) => {
                          setParamOverride(key, v);
                          persistSceneParam(effect.id, param.node_id, param.param_key, v);
                        };
                        const value =
                          typeof override === "string"
                            ? override
                            : typeof sceneVal === "string"
                              ? sceneVal
                              : typeof param.default === "string"
                                ? param.default
                                : (param.options?.[0] ?? "");
                        return (
                          <ParamSelect
                            key={key}
                            label={param.label}
                            options={param.options ?? []}
                            value={value}
                            onChange={ride}
                          />
                        );
                      })}
                    </div>
                  )}

                  <div className="fader-group__row">
                    {faderParams.map((param) => {
                      const key = `${effect.id}:${param.node_id}:${param.param_key}`;
                      const override = paramOverrides[key];
                      const sceneVal = sceneParamValue(effect.id, param.node_id, param.param_key);
                      const ride = (v: number | string) => {
                        setParamOverride(key, v);
                        persistSceneParam(effect.id, param.node_id, param.param_key, v);
                      };
                      const value =
                        typeof override === "number"
                          ? override
                          : typeof sceneVal === "number"
                            ? sceneVal
                            : typeof param.default === "number"
                              ? param.default
                              : 0;
                      return (
                        <ParamFader
                          key={key}
                          label={param.label}
                          min={param.min}
                          max={param.max}
                          value={value}
                          onChange={ride}
                          accent={accent}
                        />
                      );
                    })}
                    {effect.exposed_params.length === 0 && (
                      <p className="console-page__hint">No exposed params on this effect.</p>
                    )}
                  </div>
                </ConsoleCard>
              );
            })}
          </div>
        </ConsoleCard>

        <PlaylistPanel />
      </div>

      {editorState && (
        <div className="console-modal">
          <SceneEditor
            scene={editorState.mode === "edit" ? editorState.scene : null}
            effects={effects}
            fixtures={fixtures}
            onSave={(payload) => saveScene(payload, editorState.mode === "edit" ? editorState.scene : null)}
            onCancel={() => setEditorState(null)}
            onDelete={(id) => void deleteScene(id)}
          />
        </div>
      )}
    </div>
  );
}
