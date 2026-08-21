from typing import Any

from lumen.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from lumen.audio.analysis import NUM_BANDS
from lumen.effects.graph import EvalContext, NodeDefinition, Value

_BAND_OPTIONS = ["low", "mid", "high", *[str(i) for i in range(NUM_BANDS)]]


def _audio_level(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.audio.level)


def _audio_band(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    band = str(data.get("band", "low"))
    if band == "low":
        return float(context.audio.low)
    if band == "mid":
        return float(context.audio.mid)
    if band == "high":
        return float(context.audio.high)
    try:
        index = int(band)
    except ValueError:
        return 0.0
    bands = context.audio.bands
    if 0 <= index < len(bands):
        return float(bands[index])
    return 0.0


def _beat(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    decay_seconds = max(float(data.get("decay", 0.4)), 1e-3)
    bucket = context.state.setdefault(context.node_id, {"value": 0.0, "last_time": context.time})
    dt = max(context.time - bucket["last_time"], 0.0)
    bucket["last_time"] = context.time
    if context.audio.beat >= 0.999:
        bucket["value"] = 1.0
    else:
        bucket["value"] = max(bucket["value"] - dt / decay_seconds, 0.0)
    return bucket["value"]


def _console_hype(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.hype)


AUDIO_NODES: dict[str, NodeDefinition] = {
    "audio_level": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="audio_level",
            category="audio",
            label="Audio Level",
            outputs=[NodeSocket(key="value", type="scalar", label="Level")],
        ),
        compute=_audio_level,
    ),
    "audio_band": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="audio_band",
            category="audio",
            label="Audio Band",
            outputs=[NodeSocket(key="value", type="scalar", label="Band")],
            params=[NodeParam(key="band", type="select", default="low", options=_BAND_OPTIONS)],
        ),
        compute=_audio_band,
    ),
    "beat": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="beat",
            category="audio",
            label="Beat",
            outputs=[NodeSocket(key="value", type="scalar", label="Pulse")],
            params=[NodeParam(key="decay", type="float", default=0.4, min=0.05, max=5.0)],
        ),
        compute=_beat,
    ),
    "console_hype": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="console_hype",
            category="audio",
            label="Console Hype",
            outputs=[NodeSocket(key="value", type="scalar", label="Hype")],
        ),
        compute=_console_hype,
    ),
}
