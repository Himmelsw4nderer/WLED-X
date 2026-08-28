from typing import Any

import numpy as np

from lumen.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from lumen.effects.graph import EvalContext, NodeDefinition, Value


def _num(data: dict[str, Any], inputs: dict[str, Value], key: str, default: float) -> Value:
    return inputs.get(key, data.get(key, default))


def _add(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _num(data, inputs, "a", 0.0) + _num(data, inputs, "b", 0.0)


def _multiply(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _num(data, inputs, "a", 1.0) * _num(data, inputs, "b", 1.0)


def _subtract(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _num(data, inputs, "a", 0.0) - _num(data, inputs, "b", 0.0)


def _sine(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return np.sin(_num(data, inputs, "x", 0.0))


def _square(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """A hard on/off wave, not a curve: 1.0 for the first `duty` fraction of
    each cycle of x, 0.0 for the rest. Feed it Time*frequency for a strobe,
    or a spatial field for on/off bands along the strip."""
    x = np.asarray(_num(data, inputs, "x", 0.0), dtype=np.float32)
    duty = float(np.clip(data.get("duty", 0.5), 0.0, 1.0))
    phase = np.mod(x, 1.0)
    return np.where(phase < duty, 1.0, 0.0).astype(np.float32)


def _invert(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Flips a 0..1 value around its midpoint (1 - x): on becomes off, a
    gradient's low end becomes its high end, a fade-in becomes a fade-out."""
    return 1.0 - _num(data, inputs, "value", 0.0)


def _abs(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Absolute value: flips negative values positive, leaves positives alone."""
    return np.abs(_num(data, inputs, "value", 0.0))


def _greater_than(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """1.0 where value is above the threshold, 0.0 otherwise."""
    value = np.asarray(_num(data, inputs, "value", 0.0), dtype=np.float32)
    threshold = np.asarray(_num(data, inputs, "threshold", 0.5), dtype=np.float32)
    return np.where(value > threshold, 1.0, 0.0).astype(np.float32)


def _less_than(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """1.0 where value is below the threshold, 0.0 otherwise."""
    value = np.asarray(_num(data, inputs, "value", 0.0), dtype=np.float32)
    threshold = np.asarray(_num(data, inputs, "threshold", 0.5), dtype=np.float32)
    return np.where(value < threshold, 1.0, 0.0).astype(np.float32)


def _and_or(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Combines two 0/1 signals with AND or OR, clamped back to 0.0/1.0.

    Inputs count as "true" at >= 0.5, so this chains directly off
    Greater Than / Less Than (or any other 0/1-ish field)."""
    a_true = np.asarray(_num(data, inputs, "a", 0.0), dtype=np.float32) >= 0.5
    b_true = np.asarray(_num(data, inputs, "b", 0.0), dtype=np.float32) >= 0.5
    combined = (a_true | b_true) if data.get("mode", "and") == "or" else (a_true & b_true)
    return combined.astype(np.float32)


def _clamp(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    value = _num(data, inputs, "value", 0.0)
    lo = float(data.get("min", 0.0))
    hi = float(data.get("max", 1.0))
    return np.clip(value, lo, hi)


def _remap(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    value = _num(data, inputs, "value", 0.0)
    in_min = float(data.get("in_min", 0.0))
    in_max = float(data.get("in_max", 1.0))
    out_min = float(data.get("out_min", 0.0))
    out_max = float(data.get("out_max", 1.0))
    span = in_max - in_min
    if span == 0.0:
        return np.zeros_like(value) if isinstance(value, np.ndarray) else 0.0
    t = (value - in_min) / span
    return out_min + t * (out_max - out_min)


def _modulo(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    value = np.asarray(_num(data, inputs, "value", 0.0), dtype=np.float32)
    divisor = np.asarray(_num(data, inputs, "divisor", 1.0), dtype=np.float32)
    safe_divisor = np.where(divisor == 0, 1e-6, divisor)
    return np.mod(value, safe_divisor)


def _mix(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    a = _num(data, inputs, "a", 0.0)
    b = _num(data, inputs, "b", 1.0)
    t = _num(data, inputs, "t", 0.5)
    return a + (b - a) * t


def _constant(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(data.get("value", 0.0))


def _counter(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Counts rising edges of `trigger` (e.g. a Beat or Bass Hit pulse),
    wrapping from `max` back to 1 -- for effects that need to step through a
    longer pattern (colors, positions, a bar-count) one beat at a time
    instead of just reacting to each one. `reset` forces the count back to 0
    on its own next rising edge. State lives per node instance, keyed by
    node_id like every other stateful node (see Invert, Square's phase)."""
    max_count = max(int(float(_num(data, inputs, "max", 64.0))), 1)
    trigger = float(_num(data, inputs, "trigger", 0.0))
    reset = float(_num(data, inputs, "reset", 0.0))

    bucket = context.state.setdefault(
        context.node_id, {"count": 0, "prev_trigger": 0.0, "prev_reset": 0.0}
    )
    if reset >= 0.5 and bucket["prev_reset"] < 0.5:
        bucket["count"] = 0
    elif trigger >= 0.5 and bucket["prev_trigger"] < 0.5:
        bucket["count"] = bucket["count"] % max_count + 1
    bucket["prev_trigger"] = trigger
    bucket["prev_reset"] = reset

    count = bucket["count"]
    return {"count": float(count), "phase": count / max_count}


def _binary_node(
    node_type: str, label: str, compute: Any, a_default: float, b_default: float
) -> NodeDefinition:
    return NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type=node_type,
            category="math",
            label=label,
            inputs=[
                NodeSocket(key="a", type="field", label="A"),
                NodeSocket(key="b", type="field", label="B"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="a", type="float", default=a_default),
                NodeParam(key="b", type="float", default=b_default),
            ],
        ),
        compute=compute,
    )


MATH_NODES: dict[str, NodeDefinition] = {
    "add": _binary_node("add", "Add", _add, 0.0, 0.0),
    "multiply": _binary_node("multiply", "Multiply", _multiply, 1.0, 1.0),
    "subtract": _binary_node("subtract", "Subtract", _subtract, 0.0, 0.0),
    "sine": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="sine",
            category="math",
            label="Sine",
            inputs=[NodeSocket(key="x", type="field", label="X")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[NodeParam(key="x", type="float", default=0.0)],
        ),
        compute=_sine,
    ),
    "square": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="square",
            category="math",
            label="Square",
            inputs=[NodeSocket(key="x", type="field", label="X")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="x", type="float", default=0.0),
                NodeParam(key="duty", type="float", default=0.5, min=0.0, max=1.0),
            ],
        ),
        compute=_square,
    ),
    "invert": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="invert",
            category="math",
            label="Invert",
            inputs=[NodeSocket(key="value", type="field", label="Value")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[NodeParam(key="value", type="float", default=0.0)],
        ),
        compute=_invert,
    ),
    "abs": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="abs",
            category="math",
            label="Abs",
            inputs=[NodeSocket(key="value", type="field", label="Value")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[NodeParam(key="value", type="float", default=0.0)],
        ),
        compute=_abs,
    ),
    "greater_than": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="greater_than",
            category="math",
            label="Greater Than",
            inputs=[
                NodeSocket(key="value", type="field", label="Value"),
                NodeSocket(key="threshold", type="field", label="Threshold"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="value", type="float", default=0.0),
                NodeParam(key="threshold", type="float", default=0.5),
            ],
        ),
        compute=_greater_than,
    ),
    "less_than": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="less_than",
            category="math",
            label="Less Than",
            inputs=[
                NodeSocket(key="value", type="field", label="Value"),
                NodeSocket(key="threshold", type="field", label="Threshold"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="value", type="float", default=0.0),
                NodeParam(key="threshold", type="float", default=0.5),
            ],
        ),
        compute=_less_than,
    ),
    "and_or": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="and_or",
            category="math",
            label="And / Or",
            inputs=[
                NodeSocket(key="a", type="field", label="A"),
                NodeSocket(key="b", type="field", label="B"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="a", type="float", default=0.0),
                NodeParam(key="b", type="float", default=0.0),
                NodeParam(key="mode", type="select", default="and", options=["and", "or"]),
            ],
        ),
        compute=_and_or,
    ),
    "clamp": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="clamp",
            category="math",
            label="Clamp",
            inputs=[NodeSocket(key="value", type="field", label="Value")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="value", type="float", default=0.0),
                NodeParam(key="min", type="float", default=0.0),
                NodeParam(key="max", type="float", default=1.0),
            ],
        ),
        compute=_clamp,
    ),
    "remap": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="remap",
            category="math",
            label="Remap",
            inputs=[NodeSocket(key="value", type="field", label="Value")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="value", type="float", default=0.0),
                NodeParam(key="in_min", type="float", default=0.0),
                NodeParam(key="in_max", type="float", default=1.0),
                NodeParam(key="out_min", type="float", default=0.0),
                NodeParam(key="out_max", type="float", default=1.0),
            ],
        ),
        compute=_remap,
    ),
    "mix": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="mix",
            category="math",
            label="Mix / Lerp",
            inputs=[
                NodeSocket(key="a", type="field", label="A"),
                NodeSocket(key="b", type="field", label="B"),
                NodeSocket(key="t", type="field", label="T"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="a", type="float", default=0.0),
                NodeParam(key="b", type="float", default=1.0),
                NodeParam(key="t", type="float", default=0.5, min=0.0, max=1.0),
            ],
        ),
        compute=_mix,
    ),
    "modulo": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="modulo",
            category="math",
            label="Modulo",
            inputs=[
                NodeSocket(key="value", type="field", label="Value"),
                NodeSocket(key="divisor", type="field", label="Divisor"),
            ],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[
                NodeParam(key="value", type="float", default=0.0),
                NodeParam(key="divisor", type="float", default=1.0, min=0.0001, max=100.0),
            ],
        ),
        compute=_modulo,
    ),
    "constant": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="constant",
            category="math",
            label="Constant",
            outputs=[NodeSocket(key="value", type="scalar", label="Value")],
            params=[NodeParam(key="value", type="float", default=0.0)],
        ),
        compute=_constant,
    ),
    "counter": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="counter",
            category="math",
            label="Counter",
            inputs=[
                NodeSocket(key="trigger", type="scalar", label="Trigger"),
                NodeSocket(key="reset", type="scalar", label="Reset"),
            ],
            outputs=[
                NodeSocket(key="count", type="scalar", label="Count"),
                NodeSocket(key="phase", type="scalar", label="Phase"),
            ],
            params=[
                NodeParam(key="trigger", type="float", default=0.0),
                NodeParam(key="reset", type="float", default=0.0),
                NodeParam(key="max", type="int", default=64, min=1, max=1024),
            ],
        ),
        compute=_counter,
    ),
}
