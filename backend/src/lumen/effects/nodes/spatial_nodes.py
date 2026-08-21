"""Position/index fields derived from a fixture's LED layout, plus a
self-contained vectorized value-noise generator (no native noise dependency:
a seeded sum-of-sines, cheap enough to re-evaluate every frame)."""

from functools import lru_cache
from typing import Any

import numpy as np

from lumen.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from lumen.effects.graph import EvalContext, NodeDefinition, Value

_NOISE_OCTAVES = 4


def _normalized_axis(context: EvalContext, axis: int) -> np.ndarray:
    """0..1 along `axis`, 0 at the lowest point in the scene and 1 at the highest
    -- so effects can think in terms of "sweep from x=0 to x=1" regardless of how
    many meters wide the actual room is. Falls back to this fixture's own range
    when there's no wider scene bounding box available."""
    raw = context.positions[:, axis].astype(np.float32)
    if context.scene_bounds is not None:
        lo, hi = float(context.scene_bounds[0][axis]), float(context.scene_bounds[1][axis])
    elif raw.size:
        lo, hi = float(raw.min()), float(raw.max())
    else:
        lo, hi = 0.0, 0.0
    span = hi - lo
    if span <= 1e-9:
        return np.zeros_like(raw)
    return np.clip((raw - lo) / span, 0.0, 1.0).astype(np.float32)


def _position_x(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis(context, 0)


def _position_y(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis(context, 1)


def _position_z(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis(context, 2)


def _index_normalized(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    n = context.n
    if n <= 1:
        return np.zeros(n, dtype=np.float32)
    return np.arange(n, dtype=np.float32) / (n - 1)


def _distance_from_origin(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    return np.linalg.norm(context.positions, axis=1).astype(np.float32)


@lru_cache(maxsize=64)
def _noise_octave_params(seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    freqs = rng.uniform(0.5, 4.0, size=_NOISE_OCTAVES)
    phases = rng.uniform(0.0, 2 * np.pi, size=_NOISE_OCTAVES)
    amps = 1.0 / (np.arange(_NOISE_OCTAVES, dtype=np.float64) + 1.0)
    return freqs, phases, amps


def _noise(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    scale = float(data.get("scale", 1.0))
    seed = int(data.get("seed", 0))
    x = inputs.get("x", context.positions[:, 0])
    x_arr = np.atleast_1d(np.asarray(x, dtype=np.float32)) * scale

    freqs, phases, amps = _noise_octave_params(seed)
    value = np.zeros_like(x_arr, dtype=np.float64)
    for freq, phase, amp in zip(freqs, phases, amps, strict=True):
        value += amp * np.sin(x_arr * freq * 2 * np.pi + phase)
    value = value / amps.sum()
    return ((value + 1.0) * 0.5).astype(np.float32)


def _field_node(node_type: str, label: str, compute: Any) -> NodeDefinition:
    return NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type=node_type,
            category="spatial",
            label=label,
            outputs=[NodeSocket(key="value", type="field", label=label)],
        ),
        compute=compute,
    )


SPATIAL_NODES: dict[str, NodeDefinition] = {
    "position_x": _field_node("position_x", "Position X", _position_x),
    "position_y": _field_node("position_y", "Position Y", _position_y),
    "position_z": _field_node("position_z", "Position Z", _position_z),
    "index_normalized": _field_node("index_normalized", "Index Normalized", _index_normalized),
    "distance_from_origin": _field_node(
        "distance_from_origin", "Distance From Origin", _distance_from_origin
    ),
    "noise": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="noise",
            category="spatial",
            label="Noise",
            inputs=[NodeSocket(key="x", type="field", label="X")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="scale", type="float", default=1.0, min=0.01, max=20.0),
                NodeParam(key="seed", type="int", default=0, min=0, max=9999),
            ],
        ),
        compute=_noise,
    ),
}
