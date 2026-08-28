import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ThreeEvent } from "@react-three/fiber";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { Fixture } from "../../types";
import { distributeAlongPolyline } from "../../utils/polyline";
import { useLiveMessage } from "../../api/useLiveSocket";

const DEFAULT_LED_COLOR = new THREE.Color(0xcfd4e0);
// Reused across every LED of every frame instead of `new THREE.Color(...)`
// per LED -- at 60fps with a few hundred LEDs that's tens of thousands of
// throwaway objects a second, real GC pressure for no reason since
// setColorAt only reads the value, it doesn't keep the instance.
const SCRATCH_COLOR = new THREE.Color();
const LED_RADIUS = 0.03;
const SELECTED_LINE_COLOR = "#7c5cff";
const IDLE_LINE_COLOR = "#4a4f5c";

interface FixtureStripProps {
  fixture: Fixture;
  selected: boolean;
  onSelect: (id: number) => void;
}

export function FixtureStrip({ fixture, selected, onSelect }: FixtureStripProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const framePixels = useRef<Array<[number, number, number]> | null>(null);
  const instanceCount = Math.max(fixture.led_count, 1);

  const ledPositions = useMemo(() => {
    const positions = distributeAlongPolyline(fixture.points, fixture.led_count);
    // Must mirror the backend's led_positions(..., reverse=...) so LED i here is
    // the same physical LED i the "frame" broadcast is coloring.
    return fixture.reverse ? [...positions].reverse() : positions;
  }, [fixture.points, fixture.led_count, fixture.reverse]);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    ledPositions.forEach((p, i) => {
      dummy.position.set(p[0], p[1], p[2]);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }, [ledPositions, dummy]);

  const handleFrame = useCallback(
    (message: Record<string, unknown>) => {
      const fixtures = message.fixtures as Record<string, Array<[number, number, number]>> | undefined;
      framePixels.current = fixtures?.[fixture.id] ?? null;
    },
    [fixture.id],
  );
  useLiveMessage("frame", handleFrame);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const pixels = framePixels.current;
    for (let i = 0; i < ledPositions.length; i++) {
      const pixel = pixels?.[i];
      if (pixel) {
        // Pixel bytes from the "frame" WS message are 0-255 (see
        // engine.py's `(colors * 255).astype(uint8)`), but THREE.Color's
        // (r, g, b) constructor/setRGB takes 0-1 and does not clamp or
        // rescale out-of-range input -- feeding it raw 0-255 values made
        // every lit LED read as blown-out white instead of its real color.
        SCRATCH_COLOR.setRGB(pixel[0] / 255, pixel[1] / 255, pixel[2] / 255);
        mesh.setColorAt(i, SCRATCH_COLOR);
      } else {
        mesh.setColorAt(i, DEFAULT_LED_COLOR);
      }
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  function handleClick(e: ThreeEvent<MouseEvent>) {
    e.stopPropagation();
    onSelect(fixture.id);
  }

  return (
    <group onClick={handleClick}>
      <Line points={fixture.points} color={selected ? SELECTED_LINE_COLOR : IDLE_LINE_COLOR} lineWidth={selected ? 2 : 1} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, instanceCount]}>
        <sphereGeometry args={[LED_RADIUS, 8, 8]} />
        <meshStandardMaterial toneMapped={false} />
      </instancedMesh>
    </group>
  );
}
