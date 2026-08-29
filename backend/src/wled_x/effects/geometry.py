"""Distributes a fixture's LEDs along its polyline control points by arc
length -- two points give an evenly spaced straight strip, more points bend
the run and still space LEDs evenly along the total path length."""

import numpy as np


def led_positions(
    points: list[tuple[float, float, float]], led_count: int, reverse: bool = False
) -> np.ndarray:
    result = _led_positions_forward(points, led_count)
    return result[::-1].copy() if reverse else result


def _led_positions_forward(points: list[tuple[float, float, float]], led_count: int) -> np.ndarray:
    if led_count <= 0:
        return np.zeros((0, 3), dtype=np.float32)

    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 2:
        base = pts[0] if len(pts) else np.zeros(3)
        return np.tile(base, (led_count, 1)).astype(np.float32)

    segment_lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = cumulative[-1]

    if total_length == 0.0:
        return np.tile(pts[0], (led_count, 1)).astype(np.float32)

    targets = np.linspace(0.0, total_length, led_count) if led_count > 1 else np.array([0.0])
    result = np.empty((led_count, 3), dtype=np.float64)
    for axis in range(3):
        result[:, axis] = np.interp(targets, cumulative, pts[:, axis])
    return result.astype(np.float32)


Bounds = tuple[np.ndarray, np.ndarray]


def scene_bounds(all_points: list[list[tuple[float, float, float]]]) -> Bounds | None:
    """Bounding box (min, max) in meters across every fixture's control points --
    used to normalize PositionX/Y/Z to 0..1 across the whole installation rather
    than per-fixture. Control points alone are sufficient (and exact, not an
    approximation): every LED is interpolated between them, so the min/max over
    LEDs can never exceed the min/max over the points they're interpolated from."""
    flat = [p for points in all_points for p in points]
    if not flat:
        return None
    arr = np.asarray(flat, dtype=np.float32)
    return arr.min(axis=0), arr.max(axis=0)
