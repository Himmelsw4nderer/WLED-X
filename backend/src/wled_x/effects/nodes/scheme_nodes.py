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
    """Picks a color from the scheme, redrawing on each rising trigger edge --
    and, since a bucket only exists from the moment this node first runs, on
    every "effect start" too (the render loop wipes all per-node state on a
    scene change, and the debug preview's own bucket starts empty). Each draw
    is seeded from `context.time` (the render loop's shared clock -- the same
    value every fixture sees on a given tick) rather than a fixed `seed`
    param, so an activation is genuinely random from one to the next instead
    of always redrawing the same index -- and rather than real wall-clock
    time, which would drift by microseconds between one fixture's turn and
    the next within the *same* tick and make every fixture fed by this same
    node pick a different color, when the whole point of one shared node is
    that they match. `seed` still salts the draw so two different
    Scheme Random Color nodes triggered on the same tick don't land on the
    same color as each other."""
    scheme = context.color_scheme
    count = max(scheme.shape[0], 1)
    trigger = float(np.asarray(inputs.get("trigger", data.get("trigger", 0.0))).reshape(-1)[0])
    seed = int(data.get("seed", 0))

    bucket = context.state.setdefault(context.node_id, {"index": -1, "prev_trigger": 0.0})
    rising_edge = trigger >= 0.5 and bucket["prev_trigger"] < 0.5
    if bucket["index"] < 0 or rising_edge:
        node_salt = hash(context.node_id) & 0xFFFFFFFF
        time_seed = int(context.time * 1_000_000) & 0xFFFFFFFF
        rng = np.random.default_rng([time_seed, seed, node_salt])
        bucket["index"] = int(rng.integers(0, count))
    bucket["prev_trigger"] = trigger

    return scheme[bucket["index"] % count].astype(np.float32)


def _brightness(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """Per-pixel brightness for a color: scales `color` by `amount`, which can
    be a single float (uniform dimming) or a field (e.g. Position, Noise, or
    Distance) wired in for a brightness ramp across the strip -- the block the
    scheme colors above need for "same hue, but not every pixel at full tilt".

    `color` can arrive as a single (3,) swatch (RGB/HSV/Color Temperature with
    no field wired in) or an already-per-pixel (N, 3) field -- only broadcast
    the swatch out to (N, 3) when `amount` is itself a per-pixel field, since
    that's the only case that actually needs two different values per pixel.
    A uniform (scalar) amount must leave a (3,) swatch as (3,): forcing it to
    (1, 3) here (as this used to) reads the same via numpy broadcasting for
    every consumer *except* the final LedColor -> LED broadcast, which only
    accepts an exact (N, 3), (3,), or scalar shape and rejected (1, 3)."""
    default_color = np.zeros((context.n, 3), dtype=np.float32)
    color = np.asarray(inputs.get("color", default_color), dtype=np.float32)
    amount = np.asarray(inputs.get("amount", data.get("amount", 1.0)), dtype=np.float32)
    if amount.ndim == 1:
        if color.ndim == 1:
            color = np.tile(color, (amount.shape[0], 1))
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
