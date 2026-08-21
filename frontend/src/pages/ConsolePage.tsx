import { useEffect, useMemo, useState } from "react";
import { useConsoleStore } from "../store/useConsoleStore";
import { useSceneStore } from "../store/useSceneStore";
import { useEffectStore } from "../store/useEffectStore";
import { useFixtureStore } from "../store/useFixtureStore";
import { SceneTransport } from "../components/console/SceneTransport";
import { SceneEditor } from "../components/console/SceneEditor";
import { MasterFader } from "../components/console/MasterFader";
import { ParamFader } from "../components/console/ParamFader";
import { HitButton } from "../components/console/HitButton";
import { AudioMeter } from "../components/console/AudioMeter";
import type { Effect, Scene, SceneCreate, SceneUpdate } from "../types";
import "../components/console/console.css";

type EditorState = { mode: "create" } | { mode: "edit"; scene: Scene };

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

  return (
    <div className="page console-page">
      <div className="console-page__top">
        <SceneTransport
          scenes={scenes}
          loading={scenesLoading}
          activeSceneId={activeSceneId}
          onSelect={(scene) => void selectScene(scene)}
          onCreateNew={() => setEditorState({ mode: "create" })}
          onEdit={(scene) => setEditorState({ mode: "edit", scene })}
        />
        <MasterFader value={masterBrightness} onChange={setMasterBrightness} />
        <HitButton />
      </div>

      <div className="console-page__meter">
        <AudioMeter />
      </div>

      <div className="console-page__faders">
        {!activeScene && <p className="console-page__hint">No scene is live. Pick one above to start riding faders.</p>}
        {activeScene && liveEffects.length === 0 && (
          <p className="console-page__hint">This scene has no effect assignments yet — edit it to add some.</p>
        )}
        {liveEffects.map((effect) => (
          <section key={effect.id} className="fader-group">
            <h3>{effect.name}</h3>
            <div className="fader-group__row">
              {effect.exposed_params.map((param) => {
                const key = `${effect.id}:${param.param_key}`;
                const value = paramOverrides[key] ?? param.default;
                return (
                  <ParamFader
                    key={key}
                    label={param.label}
                    min={param.min}
                    max={param.max}
                    value={value}
                    onChange={(v) => setParamOverride(key, v)}
                  />
                );
              })}
              {effect.exposed_params.length === 0 && (
                <p className="console-page__hint">No exposed params on this effect.</p>
              )}
            </div>
          </section>
        ))}
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
