from typing import Any

from lumen.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from lumen.audio.analysis import NUM_BANDS, AudioFrame
from lumen.effects.graph import EvalContext, NodeDefinition, Value

_BAND_OPTIONS = ["low", "mid", "high", *[str(i) for i in range(NUM_BANDS)]]

# Names line up with lumen.effects.engine.PRIMARY_SOURCE / MIC_SOURCE. Kept as
# a plain literal here (rather than importing engine, which imports the node
# registry) to avoid a circular import; every audio-reading node exposes this
# so a graph can pull from the desktop mix and a live mic in parallel.
_SOURCE_OPTIONS = ["desktop", "mic"]


def _source_frame(data: dict[str, Any], context: EvalContext) -> AudioFrame:
    name = str(data.get("source", "desktop"))
    return context.audio_sources.get(name, context.audio)


def _audio_level(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(_source_frame(data, context).level)


def _audio_band(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    frame = _source_frame(data, context)
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


def _decaying_pulse(data: dict[str, Any], context: EvalContext, raw: float) -> Value:
    decay_seconds = max(float(data.get("decay", 0.4)), 1e-3)
    bucket = context.state.setdefault(context.node_id, {"value": 0.0, "last_time": context.time})
    dt = max(context.time - bucket["last_time"], 0.0)
    bucket["last_time"] = context.time
    if raw >= 0.999:
        bucket["value"] = 1.0
    else:
        bucket["value"] = max(bucket["value"] - dt / decay_seconds, 0.0)
    return bucket["value"]


def _beat(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _decaying_pulse(data, context, _source_frame(data, context).beat)


def _bass_hit(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return _decaying_pulse(data, context, _source_frame(data, context).bass_onset)


def _tempo(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(_source_frame(data, context).bpm)


def _beat_phase(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(_source_frame(data, context).beat_phase)


def _console_hype(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    return float(context.hype)


AUDIO_NODES: dict[str, NodeDefinition] = {
    "audio_level": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="audio_level",
            category="audio",
            label="Audio Level",
            outputs=[NodeSocket(key="value", type="scalar", label="Level")],
            params=[
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS)
            ],
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
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS),
            ],
        ),
        compute=_audio_band,
    ),
    "beat": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="beat",
            category="audio",
            label="Beat",
            outputs=[NodeSocket(key="value", type="scalar", label="Pulse")],
            params=[
                NodeParam(key="decay", type="float", default=0.4, min=0.05, max=5.0),
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS),
            ],
        ),
        compute=_beat,
    ),
    "bass_hit": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="bass_hit",
            category="audio",
            label="Bass Hit",
            outputs=[NodeSocket(key="value", type="scalar", label="Pulse")],
            params=[
                NodeParam(key="decay", type="float", default=0.4, min=0.05, max=5.0),
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS),
            ],
        ),
        compute=_bass_hit,
    ),
    "tempo": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="tempo",
            category="audio",
            label="Tempo (BPM)",
            outputs=[NodeSocket(key="value", type="scalar", label="BPM")],
            params=[
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS)
            ],
        ),
        compute=_tempo,
    ),
    "beat_phase": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="beat_phase",
            category="audio",
            label="Beat Phase",
            outputs=[NodeSocket(key="value", type="scalar", label="Phase")],
            params=[
                NodeParam(key="source", type="select", default="desktop", options=_SOURCE_OPTIONS)
            ],
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
