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


def _sawtooth(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """A real sawtooth (linear ramp, sharp reset), not a curve: the fractional
    part of x. Same shape as Sine -- feed it Time*frequency for an oscillator,
    or a spatial field for a repeating pattern along the strip."""
    x = np.asarray(_num(data, inputs, "x", 0.0), dtype=np.float32)
    return np.mod(x, 1.0)


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
    "sawtooth": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="sawtooth",
            category="math",
            label="Sawtooth",
            inputs=[NodeSocket(key="x", type="field", label="X")],
            outputs=[NodeSocket(key="value", type="field", label="Value")],
            params=[NodeParam(key="x", type="float", default=0.0)],
        ),
        compute=_sawtooth,
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
}
