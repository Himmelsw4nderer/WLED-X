import type { Point3 } from "../types";

function subtract(a: Point3, b: Point3): Point3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function length(v: Point3): number {
  return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
}

export function segmentLengths(points: Point3[]): number[] {
  const lengths: number[] = [];
  for (let i = 1; i < points.length; i++) {
    lengths.push(length(subtract(points[i], points[i - 1])));
  }
  return lengths;
}

export function polylineLength(points: Point3[]): number {
  return segmentLengths(points).reduce((sum, l) => sum + l, 0);
}

/**
 * Evenly distribute `count` points along a polyline by cumulative arc length.
 * For a straight 2-point fixture this reduces to a plain lerp; for more points
 * it walks the polyline segment by segment.
 */
export function distributeAlongPolyline(points: Point3[], count: number): Point3[] {
  if (count <= 0 || points.length === 0) return [];
  if (points.length === 1 || count === 1) {
    return Array.from({ length: count }, () => [...points[0]] as Point3);
  }

  const segLengths = segmentLengths(points);
  const total = segLengths.reduce((sum, l) => sum + l, 0);
  if (total === 0) return Array.from({ length: count }, () => [...points[0]] as Point3);

  const result: Point3[] = [];
  for (let i = 0; i < count; i++) {
    const target = (total * i) / (count - 1);
    result.push(pointAtDistance(points, segLengths, target));
  }
  return result;
}

function pointAtDistance(points: Point3[], segLengths: number[], target: number): Point3 {
  let traveled = 0;
  for (let i = 0; i < segLengths.length; i++) {
    const segLen = segLengths[i];
    if (traveled + segLen >= target || i === segLengths.length - 1) {
      const t = segLen === 0 ? 0 : Math.min(1, Math.max(0, (target - traveled) / segLen));
      const a = points[i];
      const b = points[i + 1];
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    }
    traveled += segLen;
  }
  return [...points[points.length - 1]] as Point3;
}
