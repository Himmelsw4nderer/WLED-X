"""Position/index fields derived from a fixture's LED layout, plus a
self-contained vectorized value-noise generator (no native noise dependency:
a seeded sum-of-sines, cheap enough to re-evaluate every frame).

Three flavors of position are exposed, all reading the same underlying LED
coordinates:
- PositionX/Y/Z: 0..1 against the whole *scene's* bounding box (all fixtures
  combined) -- for effects that should sweep across the entire installation,
  e.g. a wave that crosses every fixture in the room together.
- LocalX/Y/Z: 0..1 against *this fixture's own* bounding box only, regardless
  of where it sits in the room or how the other fixtures are laid out -- for
  effects that should look the same on every fixture independently.
- GlobalX/Y/Z: the same positions in raw, unnormalized meters -- for effects
  that need an absolute scale (e.g. a fixed 1.2m height threshold).

In the debug preview (a single synthetic strip, no wider scene) Position and
Local necessarily produce identical output -- there's only one "element" to
normalize against either way. The difference only shows with multiple real
fixtures in an actual scene."""

from functools import lru_cache
from typing import Any

import numpy as np

from wled_x.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from wled_x.effects.graph import EvalContext, NodeDefinition, Value

_NOISE_OCTAVES = 4


def _axis_range(values: np.ndarray) -> tuple[float, float]:
    if values.size:
        return float(values.min()), float(values.max())
    return 0.0, 0.0


def _normalize(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    span = hi - lo
    if span <= 1e-9:
        return np.zeros_like(raw)
    return np.clip((raw - lo) / span, 0.0, 1.0).astype(np.float32)


def _normalized_axis_scene(context: EvalContext, axis: int) -> np.ndarray:
    raw = context.positions[:, axis].astype(np.float32)
    if context.scene_bounds is not None:
        lo, hi = float(context.scene_bounds[0][axis]), float(context.scene_bounds[1][axis])
    else:
        lo, hi = _axis_range(raw)
    return _normalize(raw, lo, hi)


def _normalized_axis_local(context: EvalContext, axis: int) -> np.ndarray:
    raw = context.positions[:, axis].astype(np.float32)
    lo, hi = _axis_range(raw)
    return _normalize(raw, lo, hi)


def _position_x(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_scene(context, 0)


def _position_y(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_scene(context, 1)


def _position_z(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_scene(context, 2)


def _local_x(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_local(context, 0)


def _local_y(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_local(context, 1)


def _local_z(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _normalized_axis_local(context, 2)


def _global_x(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return context.positions[:, 0].astype(np.float32)


def _global_y(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return context.positions[:, 1].astype(np.float32)


def _global_z(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return context.positions[:, 2].astype(np.float32)


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
    "local_x": _field_node("local_x", "Local X", _local_x),
    "local_y": _field_node("local_y", "Local Y", _local_y),
    "local_z": _field_node("local_z", "Local Z", _local_z),
    "global_x": _field_node("global_x", "Global X", _global_x),
    "global_y": _field_node("global_y", "Global Y", _global_y),
    "global_z": _field_node("global_z", "Global Z", _global_z),
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
