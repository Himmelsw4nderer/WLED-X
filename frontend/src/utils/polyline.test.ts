import { describe, expect, it } from "vitest";
import { distributeAlongPolyline, polylineLength, segmentLengths } from "./polyline";
import type { Point3 } from "../types";

describe("segmentLengths / polylineLength", () => {
  it("measures a single straight segment", () => {
    const points: Point3[] = [
      [0, 0, 0],
      [3, 4, 0],
    ];
    expect(segmentLengths(points)).toEqual([5]);
    expect(polylineLength(points)).toBe(5);
  });

  it("sums multiple segments", () => {
    const points: Point3[] = [
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0],
    ];
    expect(polylineLength(points)).toBeCloseTo(2);
  });

  it("is zero for a single point", () => {
    expect(polylineLength([[0, 0, 0]])).toBe(0);
  });
});

describe("distributeAlongPolyline", () => {
  it("returns an empty array for count <= 0", () => {
    expect(distributeAlongPolyline([[0, 0, 0], [1, 0, 0]], 0)).toEqual([]);
  });

  it("returns an empty array for an empty polyline", () => {
    expect(distributeAlongPolyline([], 5)).toEqual([]);
  });

  it("repeats the single point when the polyline has only one point", () => {
    const result = distributeAlongPolyline([[2, 2, 2]], 3);
    expect(result).toEqual([
      [2, 2, 2],
      [2, 2, 2],
      [2, 2, 2],
    ]);
  });

  it("lerps evenly along a straight 2-point strip", () => {
    const points: Point3[] = [
      [0, 0, 0],
      [10, 0, 0],
    ];
    const result = distributeAlongPolyline(points, 5);
    expect(result).toEqual([
      [0, 0, 0],
      [2.5, 0, 0],
      [5, 0, 0],
      [7.5, 0, 0],
      [10, 0, 0],
    ]);
  });

  it("places a single requested LED at the start point", () => {
    const points: Point3[] = [
      [0, 0, 0],
      [10, 0, 0],
    ];
    expect(distributeAlongPolyline(points, 1)).toEqual([[0, 0, 0]]);
  });

  it("walks multiple segments by cumulative arc length", () => {
    const points: Point3[] = [
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0],
    ];
    const result = distributeAlongPolyline(points, 3);
    // total length 2: first LED at start, second at the halfway point (the corner),
    // third at the end.
    expect(result[0]).toEqual([0, 0, 0]);
    expect(result[1][0]).toBeCloseTo(1);
    expect(result[1][1]).toBeCloseTo(0);
    expect(result[2]).toEqual([1, 1, 0]);
  });

  it("does not divide by zero when all points coincide", () => {
    const points: Point3[] = [
      [1, 1, 1],
      [1, 1, 1],
    ];
    const result = distributeAlongPolyline(points, 4);
    for (const p of result) {
      expect(p).toEqual([1, 1, 1]);
    }
  });
});
