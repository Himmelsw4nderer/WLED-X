import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import { FixtureStrip } from "./FixtureStrip";
import type { Fixture } from "../../types";
import "./SceneViewer.css";

interface SceneViewerProps {
  fixtures: Fixture[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}

export function SceneViewer({ fixtures, selectedId, onSelect }: SceneViewerProps) {
  return (
    <Canvas
      className="scene-viewer"
      camera={{ position: [3, 3, 5], fov: 50 }}
      onPointerMissed={() => onSelect(null)}
    >
      <color attach="background" args={["#0b0d12"]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[4, 6, 3]} intensity={1.1} />
      <directionalLight position={[-3, 2, -4]} intensity={0.3} />
      <axesHelper args={[1]} />
      <Grid
        args={[20, 20]}
        cellColor="#262b36"
        sectionColor="#3a3f4d"
        fadeDistance={25}
        infiniteGrid
      />
      <Suspense fallback={null}>
        {fixtures.map((f) => (
          <FixtureStrip key={f.id} fixture={f} selected={f.id === selectedId} onSelect={onSelect} />
        ))}
      </Suspense>
      <OrbitControls makeDefault />
    </Canvas>
  );
}
