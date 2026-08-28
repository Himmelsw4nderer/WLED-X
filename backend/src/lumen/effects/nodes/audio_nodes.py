from typing import Any

from lumen.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from lumen.audio.analysis import NUM_BANDS
from lumen.effects.graph import EvalContext, NodeDefinition, Value

_BAND_OPTIONS = ["low", "mid", "high", *[str(i) for i in range(NUM_BANDS)]]


def _audio_level(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.audio.level)


def _audio_band(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    frame = context.audio
    band = str(data.get("band", "low"))
    if band == "low":
        return float(frame.low)
    if band == "mid":
        return float(frame.mid)
    if band == "high":
        return float(frame.high)
    try:
        index = int(band)
    except ValueError:
        return 0.0
    bands = frame.bands
    if 0 <= index < len(bands):
        return float(bands[index])
    return 0.0


def _tempo(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.audio.bpm)


def _beat_phase(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.audio.beat_phase)


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
            params=[
                NodeParam(key="band", type="select", default="low", options=_BAND_OPTIONS),
            ],
        ),
        compute=_audio_band,
    ),
    "tempo": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="tempo",
            category="audio",
            label="Tempo (BPM)",
            outputs=[NodeSocket(key="value", type="scalar", label="BPM")],
        ),
        compute=_tempo,
    ),
    "beat_phase": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="beat_phase",
            category="audio",
            label="Beat Phase",
            outputs=[NodeSocket(key="value", type="scalar", label="Phase")],
        ),
        compute=_beat_phase,
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
