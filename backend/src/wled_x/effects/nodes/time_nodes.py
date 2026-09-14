from typing import Any

import numpy as np

from wled_x.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from wled_x.effects.graph import EvalContext, NodeDefinition, Value


def _time(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    speed = float(data.get("speed", 1.0))
    return context.time * speed


def _envelope(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    """A one-shot attack/hold/decay flash, retriggered on each rising edge of
    `trigger` -- the shape a camera flash or a halogen blinder hit makes: an
    (almost) instant rise, an optional hold at full, then a fade back to 0.
    `curve` defaults to "exponential" rather than a straight ramp down because
    that's what a cooling filament (or a decaying spark) actually looks like --
    fast at first, then trailing off; "linear" is there for anything that wants
    a plain ramp instead.

    Timed off `context.time` (the render loop's shared clock) rather than an
    accumulated per-frame delta, so it's exact regardless of frame rate and
    naturally agrees across every fixture evaluating this same node on one
    tick -- the same reasoning Scheme Random Color uses for its trigger draws.
    State (the time of the last rising edge) lives per node instance, keyed by
    node_id like every other stateful node here."""
    trigger = float(np.asarray(inputs.get("trigger", data.get("trigger", 0.0))).reshape(-1)[0])
    attack = max(float(data.get("attack", 0.02)), 1e-4)
    hold = max(float(data.get("hold", 0.0)), 0.0)
    decay = max(float(data.get("decay", 0.6)), 1e-4)
    curve = str(data.get("curve", "exponential"))

    bucket = context.state.setdefault(context.node_id, {"trigger_time": None, "prev_trigger": 0.0})
    if trigger >= 0.5 and bucket["prev_trigger"] < 0.5:
        bucket["trigger_time"] = context.time
    bucket["prev_trigger"] = trigger

    trigger_time = bucket["trigger_time"]
    if trigger_time is None:
        return 0.0

    elapsed = context.time - trigger_time
    if elapsed < attack:
        return elapsed / attack
    if elapsed < attack + hold:
        return 1.0

    decay_elapsed = elapsed - attack - hold
    if curve == "linear":
        return max(0.0, 1.0 - decay_elapsed / decay)
    return float(np.exp(-3.0 * decay_elapsed / decay))


TIME_NODES: dict[str, NodeDefinition] = {
    "time": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="time",
            category="time",
            label="Time",
            outputs=[NodeSocket(key="value", type="scalar", label="Time")],
            params=[NodeParam(key="speed", type="float", default=1.0, min=0.0, max=10.0)],
        ),
        compute=_time,
    ),
    "envelope": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="envelope",
            category="time",
            label="Envelope",
            inputs=[NodeSocket(key="trigger", type="scalar", label="Trigger")],
            outputs=[NodeSocket(key="value", type="scalar", label="Value")],
            params=[
                NodeParam(key="trigger", type="float", default=0.0),
                NodeParam(key="attack", type="float", default=0.02, min=0.0, max=5.0),
                NodeParam(key="hold", type="float", default=0.0, min=0.0, max=5.0),
                NodeParam(key="decay", type="float", default=0.6, min=0.01, max=10.0),
                NodeParam(
                    key="curve", type="select", default="exponential",
                    options=["exponential", "linear"],
                ),
            ],
        ),
        compute=_envelope,
    ),
}
