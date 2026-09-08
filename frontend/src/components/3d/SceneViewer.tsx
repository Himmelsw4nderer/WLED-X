import { Suspense, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, GizmoHelper, GizmoViewport, Grid, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { FixtureStrip } from "./FixtureStrip";
import type { Fixture } from "../../types";
import "./SceneViewer.css";

interface SceneViewerProps {
  fixtures: Fixture[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}

export function SceneViewer({ fixtures, selectedId, onSelect }: SceneViewerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const ledTotal = fixtures.reduce((n, f) => n + f.led_count, 0);

  return (
    <div className="scene-viewport">
      <Canvas
        className="scene-viewer"
        camera={{ position: [4, 3.5, 6], fov: 46 }}
        onPointerMissed={() => onSelect(null)}
      >
        <color attach="background" args={["#08060d"]} />
        <fog attach="fog" args={["#08060d", 14, 36]} />
        <hemisphereLight args={["#3a3358", "#0b0a12", 0.6]} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[6, 9, 4]} intensity={1.0} />
        <directionalLight position={[-5, 3, -6]} intensity={0.35} color="#22e1ff" />

        <Grid
          args={[40, 40]}
          cellSize={1}
          cellThickness={1}
          cellColor="#2a2140"
          sectionSize={5}
          sectionThickness={1.4}
          sectionColor="#22e1ff"
          fadeDistance={40}
          fadeStrength={1.6}
          infiniteGrid
        />

        <Suspense fallback={null}>
          {fixtures.map((f) => (
            <FixtureStrip key={f.id} fixture={f} selected={f.id === selectedId} onSelect={onSelect} />
          ))}
          <ContactShadows position={[0, -0.02, 0]} opacity={0.35} scale={32} blur={2.6} far={6} color="#000000" />
        </Suspense>

        <GizmoHelper alignment="bottom-right" margin={[64, 72]}>
          <GizmoViewport axisColors={["#ff2e88", "#b4ff39", "#22e1ff"]} labelColor="#f2ecdf" />
        </GizmoHelper>

        <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.12} />
      </Canvas>

      <div className="scene-viewport__hud scene-viewport__hud--tl">
        <span className="scene-viewport__title">Room</span>
        <span className="scene-viewport__stat">
          {fixtures.length} fixture{fixtures.length === 1 ? "" : "s"} · {ledTotal} LED{ledTotal === 1 ? "" : "s"}
        </span>
      </div>

      <button
        type="button"
        className="scene-viewport__reset btn btn--small"
        onClick={() => controlsRef.current?.reset()}
      >
        Reset view
      </button>

      <div className="scene-viewport__hud scene-viewport__hud--bl">
        <span>
          <i className="scene-viewport__key scene-viewport__key--grid" /> 1 m grid
        </span>
        <span>
          <i className="scene-viewport__key scene-viewport__key--sel" /> selected
        </span>
      </div>
    </div>
  );
}
