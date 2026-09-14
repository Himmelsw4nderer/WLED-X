import type { Scene } from "../../types";

interface SceneTransportProps {
  scenes: Scene[];
  loading: boolean;
  activeSceneId: number | null;
  onSelect: (scene: Scene) => void;
  onEdit: (scene: Scene) => void;
}

export function SceneTransport({ scenes, loading, activeSceneId, onSelect, onEdit }: SceneTransportProps) {
  return (
    <div className="scene-transport">
      {loading && scenes.length === 0 ? (
        <p className="scene-transport__empty">Loading…</p>
      ) : scenes.length === 0 ? (
        <p className="scene-transport__empty">
          No scenes yet. Create one below to start driving fixtures from the console.
        </p>
      ) : (
        <ul className="scene-transport__list">
          {scenes.map((scene) => {
            const isLive = scene.id === activeSceneId;
            return (
              <li key={scene.id} className={`scene-row ${isLive ? "scene-row--live" : ""}`}>
                <button className="scene-row__select" onClick={() => onSelect(scene)}>
                  <span className={`scene-row__dot ${isLive ? "scene-row__dot--live" : ""}`} />
                  <span className="scene-row__name">{scene.name}</span>
                  <span className="scene-row__count">
                    {scene.assignments.length} assignment{scene.assignments.length === 1 ? "" : "s"}
                  </span>
                </button>
                <button className="btn btn--small btn--icon" onClick={() => onEdit(scene)}>
                  Edit
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
