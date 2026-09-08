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
fixtures in an actual scene.

LED Position / Const Position / Distance build on the same coordinates but
work with whole points instead of single axes: LED Position and Const Position
each emit an (x, y, z) point on one "vec3" wire, and Distance measures every
LED to that point under a selectable norm (L1/L2/L-inf/Lp/squared/planar),
optionally rescaled into 0..1 -- the basis for anything that animates by how
far a pixel is from somewhere."""

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


# --- Position vectors + distance metrics -------------------------------------
#
# Unlike Position/Local/Global X/Y/Z (which each emit one axis as a 0..1 or
# raw field), LED Position emits all three components on a single "vec3" wire
# so it can feed Distance without wiring three cables. Const Position emits a
# fixed point the same way. Distance then measures LED->point under a choice
# of metric and optionally rescales the result into 0..1.


def _axiswise_normalize(
    pos: np.ndarray, bounds: tuple[np.ndarray, np.ndarray] | None
) -> np.ndarray:
    out = np.empty_like(pos, dtype=np.float32)
    for axis in range(3):
        if bounds is not None:
            lo, hi = float(bounds[0][axis]), float(bounds[1][axis])
        else:
            lo, hi = _axis_range(pos[:, axis])
        out[:, axis] = _normalize(pos[:, axis], lo, hi)
    return out


def _led_position(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    pos = context.positions.astype(np.float32)
    space = str(data.get("space", "meters"))
    if space == "scene":
        return _axiswise_normalize(pos, context.scene_bounds)
    if space == "local":
        return _axiswise_normalize(pos, None)
    return pos  # "meters" -- raw fixture-local coordinates


def _const_position(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return np.array(
        [float(data.get("x", 0.0)), float(data.get("y", 0.0)), float(data.get("z", 0.0))],
        dtype=np.float32,
    )


_DISTANCE_METRICS = ("euclidean", "squared", "manhattan", "chebyshev", "minkowski", "planar_xy")
_NORMALIZE_MODES = ("radius", "radius_inv", "auto", "none")


def _metric_distance(delta: np.ndarray, metric: str, p: float) -> np.ndarray:
    """delta is (N, 3); returns (N,) under the chosen norm."""
    d = np.abs(delta.astype(np.float64))
    if metric == "manhattan":  # L1
        raw = d.sum(axis=1)
    elif metric == "chebyshev":  # L-infinity
        raw = d.max(axis=1)
    elif metric == "squared":  # L2^2 -- cheap, smooth falloff
        raw = np.square(d).sum(axis=1)
    elif metric == "minkowski":  # Lp
        p = max(p, 1e-6)
        raw = np.power(np.power(d, p).sum(axis=1), 1.0 / p)
    elif metric == "planar_xy":  # Euclidean, ignoring height (Z)
        raw = np.sqrt(d[:, 0] ** 2 + d[:, 1] ** 2)
    else:  # "euclidean" -- L2
        raw = np.sqrt(np.square(d).sum(axis=1))
    return raw.astype(np.float32)


def _distance(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    n = context.n
    a = np.atleast_2d(np.asarray(inputs.get("a", np.zeros((n, 3))), dtype=np.float32))
    b = np.atleast_2d(np.asarray(inputs.get("b", np.zeros((n, 3))), dtype=np.float32))
    delta = a - b  # broadcasts a (1,3) constant point against an (N,3) field
    if delta.shape[0] == 1 and n > 1:
        delta = np.broadcast_to(delta, (n, 3))

    raw = _metric_distance(
        delta, str(data.get("metric", "euclidean")), float(data.get("p", 3.0))
    )

    mode = str(data.get("normalize", "radius"))
    if mode == "none":
        return raw
    if mode == "auto":  # min..max across this frame's field -> 0..1
        lo, hi = _axis_range(raw)
        return _normalize(raw, lo, hi)
    radius = max(float(data.get("radius", 2.0)), 1e-6)
    scaled = np.clip(raw / radius, 0.0, 1.0).astype(np.float32)
    return (1.0 - scaled).astype(np.float32) if mode == "radius_inv" else scaled


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
    "led_position": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="led_position",
            category="spatial",
            label="LED Position",
            outputs=[NodeSocket(key="position", type="vec3", label="Position")],
            params=[
                NodeParam(
                    key="space",
                    type="select",
                    default="meters",
                    options=["meters", "scene", "local"],
                )
            ],
        ),
        compute=_led_position,
    ),
    "const_position": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="const_position",
            category="spatial",
            label="Const Position",
            outputs=[NodeSocket(key="position", type="vec3", label="Position")],
            params=[
                NodeParam(key="x", type="float", default=0.0, min=-100.0, max=100.0),
                NodeParam(key="y", type="float", default=0.0, min=-100.0, max=100.0),
                NodeParam(key="z", type="float", default=0.0, min=-100.0, max=100.0),
            ],
        ),
        compute=_const_position,
    ),
    "distance": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="distance",
            category="spatial",
            label="Distance",
            inputs=[
                NodeSocket(key="a", type="vec3", label="From"),
                NodeSocket(key="b", type="vec3", label="To"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(
                    key="metric",
                    type="select",
                    default="euclidean",
                    options=list(_DISTANCE_METRICS),
                ),
                NodeParam(key="p", type="float", default=3.0, min=0.1, max=10.0),
                NodeParam(
                    key="normalize",
                    type="select",
                    default="radius",
                    options=list(_NORMALIZE_MODES),
                ),
                NodeParam(key="radius", type="float", default=2.0, min=0.01, max=50.0),
            ],
        ),
        compute=_distance,
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
