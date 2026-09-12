"""Nodes that read from the console's active color scheme (EvalContext.color_scheme,
see wled_x.effects.color_schemes) instead of a hardcoded hue -- so a batch of
"just white" effects can share one editable palette. Scheme Color picks a
fixed (or field-driven) slot; Scheme Random Color redraws on each rising
trigger edge, using the same per-node state bucket pattern as Counter."""

from typing import Any

import numpy as np

from wled_x.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from wled_x.effects.graph import EvalContext, NodeDefinition, Value


def _scheme_color(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    scheme = context.color_scheme
    count = max(scheme.shape[0], 1)
    index = inputs.get("index", data.get("index", 0))
    idx = np.mod(np.round(np.asarray(index)).astype(np.int64), count)
    return scheme[idx].astype(np.float32)


def _scheme_random_color(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    scheme = context.color_scheme
    count = max(scheme.shape[0], 1)
    trigger = float(np.asarray(inputs.get("trigger", data.get("trigger", 0.0))).reshape(-1)[0])
    seed = int(data.get("seed", 0))

    bucket = context.state.setdefault(
        context.node_id, {"index": -1, "draw": 0, "prev_trigger": 0.0}
    )
    rising_edge = trigger >= 0.5 and bucket["prev_trigger"] < 0.5
    if bucket["index"] < 0 or rising_edge:
        rng = np.random.default_rng((seed, bucket["draw"]))
        bucket["index"] = int(rng.integers(0, count))
        bucket["draw"] += 1
    bucket["prev_trigger"] = trigger

    return scheme[bucket["index"] % count].astype(np.float32)


def _brightness(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Per-pixel brightness for a color: scales `color` by `amount`, which can
    be a single float (uniform dimming) or a field (e.g. Position, Noise, or
    Distance) wired in for a brightness ramp across the strip -- the block the
    scheme colors above need for "same hue, but not every pixel at full tilt"."""
    default_color = np.zeros((context.n, 3), dtype=np.float32)
    color = np.atleast_2d(np.asarray(inputs.get("color", default_color), dtype=np.float32))
    amount = np.asarray(inputs.get("amount", data.get("amount", 1.0)), dtype=np.float32)
    if amount.ndim == 1 and color.ndim == 2:
        amount = amount[:, None]
    return (color * amount).astype(np.float32)


SCHEME_NODES: dict[str, NodeDefinition] = {
    "scheme_color": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="scheme_color",
            category="color",
            label="Scheme Color",
            inputs=[NodeSocket(key="index", type="field", label="Index")],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[NodeParam(key="index", type="int", default=0, min=0, max=15)],
        ),
        compute=_scheme_color,
    ),
    "scheme_random_color": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="scheme_random_color",
            category="color",
            label="Scheme Random Color",
            inputs=[NodeSocket(key="trigger", type="scalar", label="Trigger")],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[
                NodeParam(key="trigger", type="float", default=0.0),
                NodeParam(key="seed", type="int", default=0, min=0, max=9999),
            ],
        ),
        compute=_scheme_random_color,
    ),
    "brightness": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="brightness",
            category="color",
            label="Brightness",
            inputs=[
                NodeSocket(key="color", type="color", label="Color"),
                NodeSocket(key="amount", type="field", label="Amount"),
            ],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[NodeParam(key="amount", type="float", default=1.0, min=0.0, max=1.0)],
        ),
        compute=_brightness,
    ),
}
