"""A handful of ready-made effect graphs, seeded straight into the DB so
there's something to look at (and copy from) besides an empty node canvas.
Each one is deliberately built from small composable nodes rather than one
big bespoke node, matching how the rest of the effect graph is meant to be
used -- see `wled_x.effects.nodes` for what each node type does.

Run with `python -m wled_x.examples` from the backend dir (with the venv
active). Safe to re-run: effects are matched and skipped by name, never
duplicated or overwritten.
"""

from sqlmodel import Session, select

from wled_x.db import engine, init_db
from wled_x.models.effect import Effect


def _node(node_id: str, node_type: str, data: dict | None = None, x: int = 0, y: int = 0) -> dict:
    """Shorthand for one reactflow-shaped node. `position` only matters for how
    the graph lays out when opened in the editor -- it never affects rendering."""
    return {"id": node_id, "type": node_type, "data": data or {}, "position": {"x": x, "y": y}}


def _edge(source: str, target: str, target_handle: str, source_handle: str = "value") -> dict:
    """Shorthand for one wire. `source_handle` defaults to "value" (every
    single-output node); pass it explicitly for multi-output nodes -- Counter's
    "phase"/"count", LED Position's "position"."""
    return {
        "id": f"{source}.{source_handle}->{target}.{target_handle}",
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
    }

# Beats-to-N counter: an 8-beat bar that refills across the strip and wraps.
# Demonstrates the Counter node (counts once-per-beat pulses, wraps at `max`)
# driving a spatial cutoff via Less Than, recolored per-LED with a rainbow HSV
# sweep. The pulse itself is Beat Phase gated by a narrow Square wave.
BEAT_BAR = Effect(
    name="Beat Bar (Counter Demo)",
    description=(
        "An 8-beat bar that fills across the strip one beat at a time, then wraps back to "
        "empty and starts again -- built from Beat Phase -> Square -> Counter -> Less Than -> HSV."
    ),
    graph={
        "nodes": [
            {
                "id": "phase1",
                "type": "beat_phase",
                "data": {},
                "position": {"x": -220, "y": 0},
            },
            {
                "id": "pulse1",
                "type": "square",
                "data": {"duty": 0.12},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "counter1",
                "type": "counter",
                "data": {"max": 8},
                "position": {"x": 220, "y": 0},
            },
            {"id": "idx1", "type": "index_normalized", "data": {}, "position": {"x": 0, "y": 160}},
            {
                "id": "lt1",
                "type": "less_than",
                "data": {"threshold": 0.5},
                "position": {"x": 440, "y": 80},
            },
            {"id": "hsv1", "type": "hsv", "data": {"s": 1.0}, "position": {"x": 660, "y": 80}},
            {"id": "out1", "type": "led_color", "data": {}, "position": {"x": 880, "y": 80}},
        ],
        "edges": [
            {
                "id": "e0",
                "source": "phase1",
                "sourceHandle": "value",
                "target": "pulse1",
                "targetHandle": "x",
            },
            {
                "id": "e1",
                "source": "pulse1",
                "sourceHandle": "value",
                "target": "counter1",
                "targetHandle": "trigger",
            },
            {
                "id": "e2",
                "source": "idx1",
                "sourceHandle": "value",
                "target": "lt1",
                "targetHandle": "value",
            },
            {
                "id": "e3",
                "source": "counter1",
                "sourceHandle": "phase",
                "target": "lt1",
                "targetHandle": "threshold",
            },
            {
                "id": "e4",
                "source": "idx1",
                "sourceHandle": "value",
                "target": "hsv1",
                "targetHandle": "h",
            },
            {
                "id": "e5",
                "source": "lt1",
                "sourceHandle": "value",
                "target": "hsv1",
                "targetHandle": "v",
            },
            {
                "id": "e6",
                "source": "hsv1",
                "sourceHandle": "value",
                "target": "out1",
                "targetHandle": "color",
            },
        ],
    },
    exposed_params=[
        {
            "node_id": "counter1",
            "param_key": "max",
            "label": "Bar Length (beats)",
            "min": 1,
            "max": 32,
            "default": 8,
        },
    ],
)

# A slow rainbow hue sweep, pulsed bright whenever the low/bass band spikes.
# Demonstrates Audio Band (low) gated by a Greater Than threshold driving
# brightness while Time drives hue.
BASS_PULSE_RAINBOW = Effect(
    name="Bass Pulse Rainbow",
    description=(
        "A slowly rotating rainbow that flashes bright whenever the low/bass band spikes -- "
        "Audio Band (low) -> Greater Than -> HSV's V, Time -> HSV's H."
    ),
    graph={
        "nodes": [
            {"id": "time1", "type": "time", "data": {"speed": 0.07}, "position": {"x": 0, "y": 0}},
            {
                "id": "band1",
                "type": "audio_band",
                "data": {"band": "low"},
                "position": {"x": 0, "y": 140},
            },
            {
                "id": "gate1",
                "type": "greater_than",
                "data": {"threshold": 0.25},
                "position": {"x": 240, "y": 140},
            },
            {"id": "hsv1", "type": "hsv", "data": {"s": 1.0}, "position": {"x": 460, "y": 60}},
            {"id": "out1", "type": "led_color", "data": {}, "position": {"x": 680, "y": 60}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "time1",
                "sourceHandle": "value",
                "target": "hsv1",
                "targetHandle": "h",
            },
            {
                "id": "e2",
                "source": "band1",
                "sourceHandle": "value",
                "target": "gate1",
                "targetHandle": "value",
            },
            {
                "id": "e3",
                "source": "gate1",
                "sourceHandle": "value",
                "target": "hsv1",
                "targetHandle": "v",
            },
            {
                "id": "e4",
                "source": "hsv1",
                "sourceHandle": "value",
                "target": "out1",
                "targetHandle": "color",
            },
        ],
    },
    exposed_params=[
        {
            "node_id": "gate1",
            "param_key": "threshold",
            "label": "Bass Sensitivity",
            "min": 0.0,
            "max": 1.0,
            "default": 0.25,
        },
        {
            "node_id": "time1",
            "param_key": "speed",
            "label": "Hue Speed",
            "min": 0.0,
            "max": 1.0,
            "default": 0.07,
        },
    ],
)


# Larson scanner ("KITT eye"): a single bright blob that glides from one end of
# the strip to the other and back, with a soft falloff on either side. The head
# position is a Sine of Time remapped to 0..1 (so it eases in and out at the
# turns instead of snapping); brightness is 1 minus the distance from the head,
# via Index Normalized -> Subtract -> Abs -> Remap -> Clamp.
SCANNER = Effect(
    name="Larson Scanner",
    description=(
        "A bright blob that sweeps end to end and back with an eased turnaround and a soft "
        "trailing falloff -- Time -> Sine -> Remap gives the head, Index -> Subtract -> Abs -> "
        "Remap -> Clamp gives the falloff, tinted by a fixed HSV hue."
    ),
    graph={
        "nodes": [
            _node("time1", "time", {"speed": 2.0}, -440, -40),
            _node("sine1", "sine", {}, -220, -40),
            _node(
                "head",
                "remap",
                {"in_min": -1.0, "in_max": 1.0, "out_min": 0.0, "out_max": 1.0},
                0,
                -40,
            ),
            _node("idx", "index_normalized", {}, -220, 120),
            _node("delta", "subtract", {}, 220, 40),
            _node("dist", "abs", {}, 440, 40),
            _node(
                "fall",
                "remap",
                {"in_min": 0.0, "in_max": 0.15, "out_min": 1.0, "out_max": 0.0},
                660,
                40,
            ),
            _node("bri", "clamp", {"min": 0.0, "max": 1.0}, 880, 40),
            _node("hsv1", "hsv", {"h": 0.55, "s": 1.0}, 1100, 40),
            _node("out1", "led_color", {}, 1320, 40),
        ],
        "edges": [
            _edge("time1", "sine1", "x"),
            _edge("sine1", "head", "value"),
            _edge("idx", "delta", "a"),
            _edge("head", "delta", "b"),
            _edge("delta", "dist", "value"),
            _edge("dist", "fall", "value"),
            _edge("fall", "bri", "value"),
            _edge("bri", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "time1", "param_key": "speed", "label": "Scan Speed",
         "min": 0.2, "max": 8.0, "default": 2.0},
        {"node_id": "fall", "param_key": "in_max", "label": "Blob Width",
         "min": 0.03, "max": 0.5, "default": 0.15},
        {"node_id": "hsv1", "param_key": "h", "label": "Color",
         "min": 0.0, "max": 1.0, "default": 0.55},
    ],
)

# Concentric ripples radiating out from a fixed point in the room, like a stone
# dropped in water. Uses the vec3 position pipeline: LED Position -> Distance to
# a Const Position gives every pixel its metres-from-source, which becomes both
# the ring pattern (Distance -> Multiply -> Sine over Time) and the hue. The
# rings breathe louder with the bass via a Mix between a dim floor and full.
RIPPLE = Effect(
    name="Room Ripple",
    description=(
        "Concentric rings spreading from a fixed point in the room, brighter on the bass -- "
        "LED Position -> Distance -> (Multiply -> Subtract Time -> Sine -> Remap) for the rings, "
        "Audio Band (low) -> Mix for the swell, Distance -> HSV hue for the colour."
    ),
    graph={
        "nodes": [
            _node("pos", "led_position", {"space": "meters"}, -460, 0),
            _node("ctr", "const_position", {"x": 0.0, "y": 1.2, "z": 0.0}, -460, 160),
            _node(
                "dist",
                "distance",
                {"metric": "euclidean", "normalize": "radius", "radius": 4.0},
                -220,
                60,
            ),
            _node("rings", "multiply", {"b": 8.0}, 20, 60),
            _node("time1", "time", {"speed": 1.5}, 20, -100),
            _node("ph", "subtract", {}, 260, 20),
            _node("sin1", "sine", {}, 480, 20),
            _node(
                "wave",
                "remap",
                {"in_min": -1.0, "in_max": 1.0, "out_min": 0.0, "out_max": 1.0},
                700,
                20,
            ),
            _node("low", "audio_band", {"band": "low"}, 480, 200),
            _node("env", "mix", {"a": 0.15, "b": 1.0}, 700, 200),
            _node("bri", "multiply", {}, 920, 100),
            _node("hsv1", "hsv", {"s": 1.0}, 1140, 100),
            _node("out1", "led_color", {}, 1360, 100),
        ],
        "edges": [
            _edge("pos", "dist", "a", source_handle="position"),
            _edge("ctr", "dist", "b", source_handle="position"),
            _edge("dist", "rings", "a"),
            _edge("rings", "ph", "a"),
            _edge("time1", "ph", "b"),
            _edge("ph", "sin1", "x"),
            _edge("sin1", "wave", "value"),
            _edge("low", "env", "t"),
            _edge("wave", "bri", "a"),
            _edge("env", "bri", "b"),
            _edge("dist", "hsv1", "h"),
            _edge("bri", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "dist", "param_key": "radius", "label": "Ripple Reach",
         "min": 0.5, "max": 10.0, "default": 4.0},
        {"node_id": "rings", "param_key": "b", "label": "Ring Count",
         "min": 1.0, "max": 24.0, "default": 8.0},
        {"node_id": "time1", "param_key": "speed", "label": "Ripple Speed",
         "min": 0.0, "max": 6.0, "default": 1.5},
    ],
)

# Starfield: sparse points flicker on and off along the strip, drifting slowly.
# A Noise field over Index + Time is thresholded by Greater Than to pick which
# pixels are "lit" this frame; the same noise sets their brightness so they
# fade rather than blink. Hi-hats (Audio Band high) lower the threshold, so the
# sky twinkles harder on busy percussion.
TWINKLE = Effect(
    name="Twinkle Starfield",
    description=(
        "Sparse warm-white stars that flicker and drift, twinkling harder on the hats -- "
        "Index -> Multiply -> Add Time -> Noise, gated by Greater Than whose threshold is "
        "pulled down by Audio Band (high)."
    ),
    graph={
        "nodes": [
            _node("idx", "index_normalized", {}, -460, 0),
            _node("spread", "multiply", {"b": 40.0}, -240, 0),
            _node("time1", "time", {"speed": 0.15}, -460, 150),
            _node("field", "add", {}, 0, 60),
            _node("noise1", "noise", {"seed": 7, "scale": 1.0}, 220, 60),
            _node("hi", "audio_band", {"band": "high"}, 0, 220),
            _node("hidip", "multiply", {"b": 0.35}, 220, 220),
            _node("thr", "subtract", {"a": 0.8}, 440, 180),
            _node("mask", "greater_than", {}, 660, 100),
            _node("spark", "multiply", {}, 880, 100),
            _node("hsv1", "hsv", {"h": 0.11, "s": 0.35}, 1100, 100),
            _node("out1", "led_color", {}, 1320, 100),
        ],
        "edges": [
            _edge("idx", "spread", "a"),
            _edge("spread", "field", "a"),
            _edge("time1", "field", "b"),
            _edge("field", "noise1", "x"),
            _edge("hi", "hidip", "a"),
            _edge("hidip", "thr", "b"),
            _edge("noise1", "mask", "value"),
            _edge("thr", "mask", "threshold"),
            _edge("mask", "spark", "a"),
            _edge("noise1", "spark", "b"),
            _edge("spark", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "spread", "param_key": "b", "label": "Star Density",
         "min": 5.0, "max": 120.0, "default": 40.0},
        {"node_id": "time1", "param_key": "speed", "label": "Drift Speed",
         "min": 0.0, "max": 2.0, "default": 0.15},
        {"node_id": "thr", "param_key": "a", "label": "Twinkle Threshold",
         "min": 0.3, "max": 0.95, "default": 0.8},
    ],
)

# Pre-drop strobe: a hard full-strip flash from a Square wave over Time, but
# scaled by Console Hype so it stays dark until you ride the "hype" fader up
# during a buildup -- then it punches in and gets brighter as hype climbs. The
# colour steps once per beat (Beat Phase -> Square -> Counter -> hue).
STROBE_DROP = Effect(
    name="Hype Strobe",
    description=(
        "A full-strip strobe that only appears when you push the console hype fader, brightening "
        "with it, colour stepping once per beat -- Time -> Square -> Multiply by Console Hype, "
        "Beat Phase -> Square -> Counter -> HSV hue."
    ),
    graph={
        "nodes": [
            _node("time1", "time", {"speed": 12.0}, -440, -40),
            _node("strobe", "square", {"duty": 0.5}, -220, -40),
            _node("hype", "console_hype", {}, -220, 120),
            _node("gate", "multiply", {}, 20, 40),
            _node("bp", "beat_phase", {}, -440, 240),
            _node("bpsq", "square", {"duty": 0.5}, -220, 240),
            _node("cnt", "counter", {"max": 6}, 20, 240),
            _node("hsv1", "hsv", {"s": 1.0}, 260, 120),
            _node("out1", "led_color", {}, 480, 120),
        ],
        "edges": [
            _edge("time1", "strobe", "x"),
            _edge("strobe", "gate", "a"),
            _edge("hype", "gate", "b"),
            _edge("bp", "bpsq", "x"),
            _edge("bpsq", "cnt", "trigger"),
            _edge("cnt", "hsv1", "h", source_handle="phase"),
            _edge("gate", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "time1", "param_key": "speed", "label": "Strobe Rate",
         "min": 2.0, "max": 30.0, "default": 12.0},
        {"node_id": "cnt", "param_key": "max", "label": "Colour Steps",
         "min": 1, "max": 16, "default": 6},
    ],
)

# Slow plasma: two Noise fields at different scales and drift rates, layered
# over Local X and Time, blended 50/50 and pushed through a Color Ramp so the
# strip melts between deep blue, magenta, hot pink and warm white. No audio --
# a calm ambient bed to sit under everything else.
PLASMA = Effect(
    name="Plasma Flow",
    description=(
        "A calm ambient wash that melts between blue, magenta, hot pink and warm white -- two "
        "Noise layers over Local X + Time at different scales, blended by Mix and coloured by a "
        "Color Ramp. No audio reactivity."
    ),
    graph={
        "nodes": [
            _node("px", "position", {"space": "local", "axis": "x"}, -460, 0),
            _node("time1", "time", {"speed": 0.15}, -460, 170),
            _node("x1", "add", {}, -220, 40),
            _node("n1", "noise", {"seed": 1, "scale": 2.5}, 20, 40),
            _node("t2", "multiply", {"b": -0.6}, -220, 220),
            _node("x2", "add", {}, 20, 220),
            _node("n2", "noise", {"seed": 2, "scale": 5.0}, 260, 220),
            _node("blend", "mix", {"t": 0.5}, 480, 120),
            _node(
                "ramp",
                "color_ramp",
                {
                    "stops": [
                        {"pos": 0.0, "color": [0.05, 0.05, 0.40]},
                        {"pos": 0.30, "color": [0.30, 0.10, 0.60]},
                        {"pos": 0.55, "color": [0.80, 0.10, 0.50]},
                        {"pos": 0.78, "color": [1.00, 0.35, 0.25]},
                        {"pos": 1.0, "color": [1.00, 0.85, 0.60]},
                    ]
                },
                700,
                120,
            ),
            _node("out1", "led_color", {}, 920, 120),
        ],
        "edges": [
            _edge("px", "x1", "a"),
            _edge("time1", "x1", "b"),
            _edge("x1", "n1", "x"),
            _edge("time1", "t2", "a"),
            _edge("px", "x2", "a"),
            _edge("t2", "x2", "b"),
            _edge("x2", "n2", "x"),
            _edge("n1", "blend", "a"),
            _edge("n2", "blend", "b"),
            _edge("blend", "ramp", "position"),
            _edge("ramp", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "time1", "param_key": "speed", "label": "Flow Speed",
         "min": 0.0, "max": 1.0, "default": 0.15},
        {"node_id": "n1", "param_key": "scale", "label": "Plasma Scale",
         "min": 0.5, "max": 10.0, "default": 2.5},
    ],
)


# Beat wipe: a bright band whose centre sits exactly on Beat Phase, so it sweeps
# across the strip once per beat (Position X between Beat Phase +/- width, gated
# by And). The colour steps once per beat off a Counter driven straight by Beat
# Phase, and the downbeat (Beat Phase < 0.06) fires a white full-strip flash --
# Subtract 1 - flash drives saturation to 0 so the flash reads white.
BEAT_WIPE = Effect(
    name="Beat Wipe",
    description=(
        "A lit band that rides Beat Phase across the strip once per beat, colour stepping each "
        "beat off a Counter, with a white flash on every downbeat -- Position X vs Beat Phase +/- "
        "width via Greater/Less/And, Counter -> hue, Less Than(Beat Phase) -> flash."
    ),
    graph={
        "nodes": [
            _node("bp", "beat_phase", {}, -640, 120),
            _node("w", "constant", {"value": 0.15}, -640, 300),
            _node("lo", "subtract", {}, -400, 60),
            _node("hi", "add", {}, -400, 200),
            _node("px", "position", {"space": "scene", "axis": "x"}, -400, -80),
            _node("g", "greater_than", {}, -160, -20),
            _node("l", "less_than", {}, -160, 140),
            _node("band", "and_or", {"mode": "and"}, 60, 60),
            _node("flash", "less_than", {"threshold": 0.06}, -160, 300),
            _node("v", "and_or", {"mode": "or"}, 280, 160),
            _node("cnt", "counter", {"max": 8}, -400, 420),
            _node("hue", "multiply", {"b": 0.125}, -160, 420),
            _node("sat", "subtract", {"a": 1.0}, 280, 320),
            _node("hsv1", "hsv", {}, 520, 200),
            _node("out1", "led_color", {}, 740, 200),
        ],
        "edges": [
            _edge("bp", "lo", "a"),
            _edge("bp", "hi", "a"),
            _edge("w", "lo", "b"),
            _edge("w", "hi", "b"),
            _edge("px", "g", "value"),
            _edge("px", "l", "value"),
            _edge("lo", "g", "threshold"),
            _edge("hi", "l", "threshold"),
            _edge("g", "band", "a"),
            _edge("l", "band", "b"),
            _edge("bp", "flash", "value"),
            _edge("band", "v", "a"),
            _edge("flash", "v", "b"),
            _edge("bp", "cnt", "trigger"),
            _edge("cnt", "hue", "a", source_handle="count"),
            _edge("flash", "sat", "b"),
            _edge("hue", "hsv1", "h"),
            _edge("sat", "hsv1", "s"),
            _edge("v", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "w", "param_key": "value", "label": "Band Width",
         "min": 0.02, "max": 0.5, "default": 0.15},
        {"node_id": "cnt", "param_key": "max", "label": "Colours",
         "min": 1, "max": 16, "default": 8},
        {"node_id": "px", "param_key": "axis", "label": "Sweep Axis",
         "options": ["x", "y", "z", "xy", "xz", "yz", "xyz"], "default": "x"},
    ],
)

# Zone chase: the strip is split into 4 quarters (Index x 4); a Counter lights
# one quarter at a time and advances on every 8th note -- Beat Phase x 2 ->
# Modulo 1 -> Less Than makes the 8th-note pulse that clocks the Counter. Each
# quarter takes the Counter's phase as its hue, and the downbeat flashes the
# whole strip white. Straight out of "4 heigts", but stepping twice as fast.
ZONE_CHASE = Effect(
    name="Zone Chase",
    description=(
        "Four strip quarters, one lit at a time, stepping on every 8th note -- Beat Phase x 2 -> "
        "Modulo -> Less Than clocks a Counter, Index x 4 vs Counter via Greater/Less/And picks "
        "the quarter, Counter phase -> hue, downbeat -> white flash."
    ),
    graph={
        "nodes": [
            _node("bp", "beat_phase", {}, -720, 160),
            _node("mul2", "multiply", {"b": 2.0}, -520, 160),
            _node("saw", "modulo", {"divisor": 1.0}, -340, 160),
            _node("p8", "less_than", {"threshold": 0.5}, -160, 160),
            _node("cnt", "counter", {"max": 4}, 40, 160),
            _node("idx", "index_normalized", {}, -520, -40),
            _node("izone", "multiply", {"b": 4.0}, -340, -40),
            _node("lo", "subtract", {"b": 1.0}, 240, 20),
            _node("g", "greater_than", {}, 440, -40),
            _node("l", "less_than", {}, 440, 120),
            _node("zone", "and_or", {"mode": "and"}, 640, 40),
            _node("flash", "less_than", {"threshold": 0.08}, 240, 260),
            _node("v", "and_or", {"mode": "or"}, 840, 140),
            _node("hue", "multiply", {"b": 0.85}, 240, 400),
            _node("sat", "subtract", {"a": 1.0}, 640, 300),
            _node("hsv1", "hsv", {}, 1040, 180),
            _node("out1", "led_color", {}, 1260, 180),
        ],
        "edges": [
            _edge("bp", "mul2", "a"),
            _edge("mul2", "saw", "value"),
            _edge("saw", "p8", "value"),
            _edge("p8", "cnt", "trigger"),
            _edge("idx", "izone", "a"),
            _edge("cnt", "lo", "a", source_handle="count"),
            _edge("izone", "g", "value"),
            _edge("lo", "g", "threshold"),
            _edge("izone", "l", "value"),
            _edge("cnt", "l", "threshold", source_handle="count"),
            _edge("g", "zone", "a"),
            _edge("l", "zone", "b"),
            _edge("bp", "flash", "value"),
            _edge("zone", "v", "a"),
            _edge("flash", "v", "b"),
            _edge("cnt", "hue", "a", source_handle="phase"),
            _edge("flash", "sat", "b"),
            _edge("hue", "hsv1", "h"),
            _edge("sat", "hsv1", "s"),
            _edge("v", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "p8", "param_key": "threshold", "label": "8th Gate",
         "min": 0.05, "max": 0.9, "default": 0.5},
        {"node_id": "hue", "param_key": "b", "label": "Hue Spread",
         "min": 0.0, "max": 1.0, "default": 0.85},
    ],
)

# Phrase riser: a 16-beat buildup. A Counter clocked by Beat Phase counts beats
# across the phrase; its phase (count / 16) is a Less Than cutoff that fills the
# strip a little further each beat, and also the hue, so the colour climbs as it
# fills. Every 4th beat (Modulo count by 4) punches a white accent flash.
PHRASE_RISER = Effect(
    name="Phrase Riser",
    description=(
        "A 16-beat buildup: a Counter on Beat Phase fills the strip one beat at a time (phase "
        "-> Less Than cutoff), hue climbing with the fill, and a white accent flash on every 4th "
        "beat -- Modulo(count, 4) & Less Than(Beat Phase)."
    ),
    graph={
        "nodes": [
            _node("bp", "beat_phase", {}, -640, 120),
            _node("cnt", "counter", {"max": 16}, -440, 120),
            _node("idx", "index_normalized", {}, -440, -60),
            _node("fill", "less_than", {}, -160, -20),
            _node("m4", "modulo", {"divisor": 4.0}, -200, 260),
            _node("is4", "less_than", {"threshold": 0.5}, 0, 260),
            _node("dbg", "less_than", {"threshold": 0.12}, 0, 400),
            _node("accent", "and_or", {"mode": "and"}, 220, 320),
            _node("v", "and_or", {"mode": "or"}, 440, 120),
            _node("hue", "multiply", {"b": 0.66}, -160, 120),
            _node("sat", "subtract", {"a": 1.0}, 440, 300),
            _node("hsv1", "hsv", {}, 660, 180),
            _node("out1", "led_color", {}, 880, 180),
        ],
        "edges": [
            _edge("bp", "cnt", "trigger"),
            _edge("idx", "fill", "value"),
            _edge("cnt", "fill", "threshold", source_handle="phase"),
            _edge("cnt", "hue", "a", source_handle="phase"),
            _edge("cnt", "m4", "value", source_handle="count"),
            _edge("m4", "is4", "value"),
            _edge("bp", "dbg", "value"),
            _edge("is4", "accent", "a"),
            _edge("dbg", "accent", "b"),
            _edge("fill", "v", "a"),
            _edge("accent", "v", "b"),
            _edge("accent", "sat", "b"),
            _edge("hue", "hsv1", "h"),
            _edge("sat", "hsv1", "s"),
            _edge("v", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "cnt", "param_key": "max", "label": "Phrase (beats)",
         "min": 4, "max": 32, "default": 16},
        {"node_id": "hue", "param_key": "b", "label": "Hue Rise",
         "min": 0.0, "max": 1.0, "default": 0.66},
    ],
)

# Beat bounce: a Larson blob that jumps one segment per beat instead of gliding.
# A Counter clocked by Beat Phase runs 0..16; Subtract/Abs fold that into a
# 0..8..0 triangle, so the head steps to the far end over 8 beats and back over
# the next 8. Brightness is 1 - distance from the head (Index -> Subtract -> Abs
# -> Remap -> Clamp); hue steps with the raw count.
BEAT_BOUNCE = Effect(
    name="Beat Bounce",
    description=(
        "A bright blob that hops one segment per beat, out to the far end over 8 beats and back "
        "-- Counter on Beat Phase -> Subtract/Abs triangle -> head, Index -> Subtract -> Abs -> "
        "Remap -> Clamp for the falloff, count -> hue."
    ),
    graph={
        "nodes": [
            _node("bp", "beat_phase", {}, -640, 80),
            _node("cnt", "counter", {"max": 16}, -440, 80),
            _node("c8", "subtract", {"b": 8.0}, -240, 80),
            _node("ac", "abs", {}, -60, 80),
            _node("tri", "subtract", {"a": 8.0}, 120, 80),
            _node("head", "multiply", {"b": 0.125}, 300, 80),
            _node("idx", "index_normalized", {}, 120, -100),
            _node("d", "subtract", {}, 480, -20),
            _node("ad", "abs", {}, 660, -20),
            _node(
                "fall",
                "remap",
                {"in_min": 0.0, "in_max": 0.18, "out_min": 1.0, "out_max": 0.0},
                840,
                -20,
            ),
            _node("bri", "clamp", {"min": 0.0, "max": 1.0}, 1020, -20),
            _node("hue", "multiply", {"b": 0.0625}, 300, 260),
            _node("hsv1", "hsv", {"s": 1.0}, 1220, 60),
            _node("out1", "led_color", {}, 1440, 60),
        ],
        "edges": [
            _edge("bp", "cnt", "trigger"),
            _edge("cnt", "c8", "a", source_handle="count"),
            _edge("c8", "ac", "value"),
            _edge("ac", "tri", "b"),
            _edge("tri", "head", "a"),
            _edge("idx", "d", "a"),
            _edge("head", "d", "b"),
            _edge("d", "ad", "value"),
            _edge("ad", "fall", "value"),
            _edge("fall", "bri", "value"),
            _edge("cnt", "hue", "a", source_handle="count"),
            _edge("hue", "hsv1", "h"),
            _edge("bri", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "fall", "param_key": "in_max", "label": "Blob Width",
         "min": 0.03, "max": 0.5, "default": 0.18},
        {"node_id": "cnt", "param_key": "max", "label": "Bounce Length (beats)",
         "min": 2, "max": 32, "default": 16},
    ],
)


# --- Distance-from-room-centre + beat energy -------------------------------
#
# All three measure every LED's distance to one point in the room -- LED
# Position -> Distance -> Const Position, with the centre's X/Y/Z exposed as
# console faders so you can place it wherever the middle of your space is.
# Distance is normalized 0..1 against a "Room Size" radius (0 at the centre,
# 1 at the walls), so the look is the same regardless of how big the room is.


# Core Shockwave: a bright shell that blasts out from the centre on every beat
# and again on the half-beat. Beat Phase (0..1 per beat) *is* the wavefront
# radius -- an LED lights when its distance-from-centre is within Shell Width of
# Beat Phase. A second wavefront runs half a beat out of phase for double-time
# energy, the whole rainbow rotates one step per beat off a Counter, and the
# audio level pumps overall brightness.
CORE_SHOCKWAVE = Effect(
    name="Core Shockwave",
    description=(
        "Rainbow shells firing out from a point in the room on every beat and half-beat, "
        "brightness pumping with the audio level -- Distance-from-centre vs Beat Phase +/- width "
        "(and vs Modulo(Beat Phase + 0.5)), Counter -> hue rotation, Audio Level -> Mix gain."
    ),
    graph={
        "nodes": [
            _node("pos", "led_position", {"space": "meters"}, -820, 0),
            _node("ctr", "const_position", {"x": 0.0, "y": 1.2, "z": 0.0}, -820, 160),
            _node(
                "dist",
                "distance",
                {"metric": "euclidean", "normalize": "radius", "radius": 3.0},
                -600,
                60,
            ),
            _node("bp", "beat_phase", {}, -600, 240),
            _node("d1", "subtract", {}, -360, 0),
            _node("a1", "abs", {}, -180, 0),
            _node("shell1", "less_than", {"threshold": 0.12}, 0, 0),
            _node("half", "add", {"b": 0.5}, -600, 400),
            _node("hmod", "modulo", {"divisor": 1.0}, -420, 400),
            _node("d2", "subtract", {}, -240, 200),
            _node("a2", "abs", {}, -60, 200),
            _node("shell2", "less_than", {"threshold": 0.08}, 120, 200),
            _node("shell", "and_or", {"mode": "or"}, 320, 100),
            _node("lvl", "audio_level", {}, 120, 380),
            _node("gain", "mix", {"a": 0.35, "b": 1.0}, 320, 380),
            _node("vout", "multiply", {}, 540, 200),
            _node("cnt", "counter", {"max": 5}, -360, 560),
            _node("dnh", "multiply", {"b": 0.5}, -160, 560),
            _node("hue", "add", {}, 60, 560),
            _node("hsv1", "hsv", {"s": 1.0}, 760, 260),
            _node("out1", "led_color", {}, 980, 260),
        ],
        "edges": [
            _edge("pos", "dist", "a", source_handle="position"),
            _edge("ctr", "dist", "b", source_handle="position"),
            _edge("dist", "d1", "a"),
            _edge("bp", "d1", "b"),
            _edge("d1", "a1", "value"),
            _edge("a1", "shell1", "value"),
            _edge("bp", "half", "a"),
            _edge("half", "hmod", "value"),
            _edge("dist", "d2", "a"),
            _edge("hmod", "d2", "b"),
            _edge("d2", "a2", "value"),
            _edge("a2", "shell2", "value"),
            _edge("shell1", "shell", "a"),
            _edge("shell2", "shell", "b"),
            _edge("lvl", "gain", "t"),
            _edge("shell", "vout", "a"),
            _edge("gain", "vout", "b"),
            _edge("bp", "cnt", "trigger"),
            _edge("dist", "dnh", "a"),
            _edge("dnh", "hue", "a"),
            _edge("cnt", "hue", "b", source_handle="phase"),
            _edge("hue", "hsv1", "h"),
            _edge("vout", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "ctr", "param_key": "x", "label": "Centre X",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "ctr", "param_key": "y", "label": "Centre Y",
         "min": 0.0, "max": 5.0, "default": 1.2},
        {"node_id": "ctr", "param_key": "z", "label": "Centre Z",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "dist", "param_key": "radius", "label": "Room Size",
         "min": 0.5, "max": 15.0, "default": 3.0},
        {"node_id": "shell1", "param_key": "threshold", "label": "Shell Width",
         "min": 0.03, "max": 0.4, "default": 0.12},
    ],
)

# Bass Bloom: the room floods with light from the centre outward, the fill
# radius driven by the bass (Audio Band low -> Mix -> Less Than cutoff on the
# distance field), so a kick punches light to the walls and it recedes. On top,
# the innermost core strobes twice per beat (Beat Phase x 2 -> Modulo -> Less
# Than, gated to the centre), and the hue steps once per beat.
BASS_BLOOM = Effect(
    name="Bass Bloom",
    description=(
        "Light floods out from a point in the room on every kick and pulls back -- Audio Band "
        "(low) -> Mix -> Less Than cutoff on Distance-from-centre -- while the core strobes twice "
        "a beat (Beat Phase x 2 -> Modulo -> Less Than) and a Counter steps the hue."
    ),
    graph={
        "nodes": [
            _node("pos", "led_position", {"space": "meters"}, -820, 0),
            _node("ctr", "const_position", {"x": 0.0, "y": 1.2, "z": 0.0}, -820, 160),
            _node(
                "dist",
                "distance",
                {"metric": "euclidean", "normalize": "radius", "radius": 3.0},
                -600,
                60,
            ),
            _node("low", "audio_band", {"band": "low"}, -600, 240),
            _node("reach", "mix", {"a": 0.15, "b": 1.1}, -400, 240),
            _node("flood", "less_than", {}, -180, 100),
            _node("bp", "beat_phase", {}, -600, 420),
            _node("bp2", "multiply", {"b": 2.0}, -400, 420),
            _node("saw", "modulo", {"divisor": 1.0}, -220, 420),
            _node("cstrobe", "less_than", {"threshold": 0.2}, -40, 420),
            _node("inner", "less_than", {"threshold": 0.28}, -180, 260),
            _node("cflash", "and_or", {"mode": "and"}, 180, 340),
            _node("vout", "and_or", {"mode": "or"}, 400, 180),
            _node("cnt", "counter", {"max": 8}, -400, 580),
            _node("dnh", "multiply", {"b": 0.5}, -200, 580),
            _node("hue", "add", {}, 20, 580),
            _node("hsv1", "hsv", {"s": 1.0}, 620, 260),
            _node("out1", "led_color", {}, 840, 260),
        ],
        "edges": [
            _edge("pos", "dist", "a", source_handle="position"),
            _edge("ctr", "dist", "b", source_handle="position"),
            _edge("low", "reach", "t"),
            _edge("dist", "flood", "value"),
            _edge("reach", "flood", "threshold"),
            _edge("bp", "bp2", "a"),
            _edge("bp2", "saw", "value"),
            _edge("saw", "cstrobe", "value"),
            _edge("dist", "inner", "value"),
            _edge("cstrobe", "cflash", "a"),
            _edge("inner", "cflash", "b"),
            _edge("flood", "vout", "a"),
            _edge("cflash", "vout", "b"),
            _edge("bp", "cnt", "trigger"),
            _edge("dist", "dnh", "a"),
            _edge("dnh", "hue", "a"),
            _edge("cnt", "hue", "b", source_handle="phase"),
            _edge("hue", "hsv1", "h"),
            _edge("vout", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "ctr", "param_key": "x", "label": "Centre X",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "ctr", "param_key": "y", "label": "Centre Y",
         "min": 0.0, "max": 5.0, "default": 1.2},
        {"node_id": "ctr", "param_key": "z", "label": "Centre Z",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "dist", "param_key": "radius", "label": "Room Size",
         "min": 0.5, "max": 15.0, "default": 3.0},
        {"node_id": "reach", "param_key": "b", "label": "Bass Reach",
         "min": 0.3, "max": 1.5, "default": 1.1},
    ],
)

# Ring Slammer: crisp concentric rings scrolling out from the centre, their
# outward speed locked to the beat (Beat Phase drives the scroll term, so the
# rings move exactly N per beat). Greater Than hard-edges the Sine into sharp
# bands, and every downbeat (Less Than Beat Phase) slams the whole room white.
RING_SLAMMER = Effect(
    name="Ring Slammer",
    description=(
        "Sharp concentric rings pumping out from a point in the room, their speed locked to the "
        "tempo, with a white full-room slam on every downbeat -- Distance x density - Beat Phase "
        "x speed -> Sine -> Greater Than, Less Than(Beat Phase) -> slam, Counter -> hue."
    ),
    graph={
        "nodes": [
            _node("pos", "led_position", {"space": "meters"}, -820, 0),
            _node("ctr", "const_position", {"x": 0.0, "y": 1.2, "z": 0.0}, -820, 160),
            _node(
                "dist",
                "distance",
                {"metric": "euclidean", "normalize": "radius", "radius": 3.0},
                -600,
                60,
            ),
            _node("rp", "multiply", {"b": 8.0}, -380, 40),
            _node("bp", "beat_phase", {}, -600, 260),
            _node("scroll", "multiply", {"b": 2.0}, -380, 260),
            _node("ph", "subtract", {}, -160, 120),
            _node("sin1", "sine", {}, 20, 120),
            _node(
                "wave",
                "remap",
                {"in_min": -1.0, "in_max": 1.0, "out_min": 0.0, "out_max": 1.0},
                200,
                120,
            ),
            _node("rings", "greater_than", {"threshold": 0.55}, 380, 120),
            _node("slam", "less_than", {"threshold": 0.1}, 200, 320),
            _node("vout", "and_or", {"mode": "or"}, 580, 200),
            _node("sat", "subtract", {"a": 1.0}, 580, 360),
            _node("cnt", "counter", {"max": 6}, -380, 460),
            _node("dnh", "multiply", {"b": 0.2}, -160, 460),
            _node("hue", "add", {}, 60, 460),
            _node("hsv1", "hsv", {}, 820, 260),
            _node("out1", "led_color", {}, 1040, 260),
        ],
        "edges": [
            _edge("pos", "dist", "a", source_handle="position"),
            _edge("ctr", "dist", "b", source_handle="position"),
            _edge("dist", "rp", "a"),
            _edge("bp", "scroll", "a"),
            _edge("rp", "ph", "a"),
            _edge("scroll", "ph", "b"),
            _edge("ph", "sin1", "x"),
            _edge("sin1", "wave", "value"),
            _edge("wave", "rings", "value"),
            _edge("bp", "slam", "value"),
            _edge("rings", "vout", "a"),
            _edge("slam", "vout", "b"),
            _edge("slam", "sat", "b"),
            _edge("bp", "cnt", "trigger"),
            _edge("dist", "dnh", "a"),
            _edge("dnh", "hue", "a"),
            _edge("cnt", "hue", "b", source_handle="phase"),
            _edge("hue", "hsv1", "h"),
            _edge("sat", "hsv1", "s"),
            _edge("vout", "hsv1", "v"),
            _edge("hsv1", "out1", "color"),
        ],
    },
    exposed_params=[
        {"node_id": "ctr", "param_key": "x", "label": "Centre X",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "ctr", "param_key": "y", "label": "Centre Y",
         "min": 0.0, "max": 5.0, "default": 1.2},
        {"node_id": "ctr", "param_key": "z", "label": "Centre Z",
         "min": -10.0, "max": 10.0, "default": 0.0},
        {"node_id": "rp", "param_key": "b", "label": "Ring Density",
         "min": 1.0, "max": 24.0, "default": 8.0},
        {"node_id": "scroll", "param_key": "b", "label": "Rings / Beat",
         "min": 0.0, "max": 12.0, "default": 2.0},
    ],
)


# --- Console-authored effects, promoted to shipped defaults ------------------
#
# Built by hand in the node editor rather than written directly as Python (like
# everything above), then exported here verbatim so they ship for everyone --
# same seeding/skip-by-name mechanism as the rest of this file.

RANDOM_STROBE = Effect(
    name="Random Strobe",
    description=(
        "A narrow band scans the strip (Position X vs. a Time-driven edge through Square), only "
        "strobing into view on a twice-per-beat pulse (Beat Phase x2 -> Modulo -> Less Than) -- "
        "Scheme Random Color redraws on that same pulse."
    ),
    graph={
        "nodes": [
            {
                "id": "led_color-382da588",
                "type": "led_color",
                "position": {
                    "x": 1662.3868844059216,
                    "y": 94.19312965815334
                },
                "data": {}
            },
            {
                "id": "time-35112d8c",
                "type": "time",
                "position": {
                    "x": -646.8123583692102,
                    "y": -98.93332099242065
                },
                "data": {
                    "speed": 2
                }
            },
            {
                "id": "multiply-6169e4c7",
                "type": "multiply",
                "position": {
                    "x": -402.90602536626216,
                    "y": -100.48266170050886
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            },
            {
                "id": "subtract-f6497a78",
                "type": "subtract",
                "position": {
                    "x": 139.12714384291831,
                    "y": -309.2658852915016
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "position_x-61c6c3f4",
                "type": "position",
                "position": {
                    "x": -223.4519286289082,
                    "y": -492.1851468084791
                },
                "data": {
                    "space": "scene",
                    "axis": "x"
                }
            },
            {
                "id": "square-1a3c51ff",
                "type": "square",
                "position": {
                    "x": 408.6512241024837,
                    "y": -185.59715724965463
                },
                "data": {
                    "x": 0,
                    "duty": 0.6
                }
            },
            {
                "id": "multiply-4e71d26e",
                "type": "multiply",
                "position": {
                    "x": 661.8127682302711,
                    "y": 101.36039238442795
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            },
            {
                "id": "beat_phase-7008f124",
                "type": "beat_phase",
                "position": {
                    "x": -777.6531360918843,
                    "y": 331.3816693696658
                },
                "data": {}
            },
            {
                "id": "less_than-c6ad4ce4",
                "type": "less_than",
                "position": {
                    "x": -71.21254904312764,
                    "y": 542.0765444737133
                },
                "data": {
                    "value": 0,
                    "threshold": 0.05
                }
            },
            {
                "id": "multiply-f52435e3",
                "type": "multiply",
                "position": {
                    "x": -559.8751253820502,
                    "y": 546.4292976066315
                },
                "data": {
                    "a": 1,
                    "b": 2
                }
            },
            {
                "id": "modulo-226ee494",
                "type": "modulo",
                "position": {
                    "x": -313.924490831671,
                    "y": 541.494739947905
                },
                "data": {
                    "value": 0,
                    "divisor": 1
                }
            },
            {
                "id": "scheme_random_color-869bfd4c",
                "type": "scheme_random_color",
                "position": {
                    "x": 801.4951485391414,
                    "y": -112.79899315245135
                },
                "data": {
                    "trigger": 0,
                    "seed": 11
                }
            },
            {
                "id": "brightness-88168ae9",
                "type": "brightness",
                "position": {
                    "x": 1154.7730120036204,
                    "y": 106.4314230288071
                },
                "data": {
                    "amount": 1
                }
            }
        ],
        "edges": [
            {
                "id": "e-time-35112d8c-value-multiply-6169e4c7-a-ud6jdh",
                "source": "time-35112d8c",
                "sourceHandle": "value",
                "target": "multiply-6169e4c7",
                "targetHandle": "a"
            },
            {
                "id": "e-position_x-61c6c3f4-value-subtract-f6497a78-a-3ugjnz",
                "source": "position_x-61c6c3f4",
                "sourceHandle": "value",
                "target": "subtract-f6497a78",
                "targetHandle": "a"
            },
            {
                "id": "e-subtract-f6497a78-value-square-1a3c51ff-x-vehonb",
                "source": "subtract-f6497a78",
                "sourceHandle": "value",
                "target": "square-1a3c51ff",
                "targetHandle": "x"
            },
            {
                "id": "e-square-1a3c51ff-value-multiply-4e71d26e-a-c38tci",
                "source": "square-1a3c51ff",
                "sourceHandle": "value",
                "target": "multiply-4e71d26e",
                "targetHandle": "a"
            },
            {
                "id": "e-less_than-c6ad4ce4-value-multiply-4e71d26e-b-9j5a5q",
                "source": "less_than-c6ad4ce4",
                "sourceHandle": "value",
                "target": "multiply-4e71d26e",
                "targetHandle": "b"
            },
            {
                "id": "e-beat_phase-7008f124-value-multiply-f52435e3-a-4qitur",
                "source": "beat_phase-7008f124",
                "sourceHandle": "value",
                "target": "multiply-f52435e3",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-f52435e3-value-modulo-226ee494-value-oj0muk",
                "source": "multiply-f52435e3",
                "sourceHandle": "value",
                "target": "modulo-226ee494",
                "targetHandle": "value"
            },
            {
                "id": "e-modulo-226ee494-value-less_than-c6ad4ce4-value-3f40kr",
                "source": "modulo-226ee494",
                "sourceHandle": "value",
                "target": "less_than-c6ad4ce4",
                "targetHandle": "value"
            },
            {
                "id": "e-multiply-6169e4c7-value-subtract-f6497a78-b-o29po4",
                "source": "multiply-6169e4c7",
                "sourceHandle": "value",
                "target": "subtract-f6497a78",
                "targetHandle": "b"
            },
            {
                "id": "e-scheme_random_color-869bfd4c-value-brightness-88168ae9-color-njjzkv",
                "source": "scheme_random_color-869bfd4c",
                "sourceHandle": "value",
                "target": "brightness-88168ae9",
                "targetHandle": "color"
            },
            {
                "id": "e-multiply-4e71d26e-value-brightness-88168ae9-amount-io4e4p",
                "source": "multiply-4e71d26e",
                "sourceHandle": "value",
                "target": "brightness-88168ae9",
                "targetHandle": "amount"
            },
            {
                "id": "e-brightness-88168ae9-value-led_color-382da588-color-1ffqf9",
                "source": "brightness-88168ae9",
                "sourceHandle": "value",
                "target": "led_color-382da588",
                "targetHandle": "color"
            }
        ]
    },
    exposed_params=[],
)


SIDE_PHASE = Effect(
    name="Side Phase",
    description=(
        "A lit band rides Beat Phase across the strip like Beat Wipe, but Position X is mirrored (1 - "
        "x) first so it sweeps in from the opposite end -- Greater/Less Than gate a window (width "
        "exposed) around Beat Phase, tinted by one fixed Scheme Random Color pick."
    ),
    graph={
        "nodes": [
            {
                "id": "beat_phase-e7a511d3",
                "type": "beat_phase",
                "position": {
                    "x": -107.47577445873173,
                    "y": 297.2794307721846
                },
                "data": {
                    "source": "desktop"
                }
            },
            {
                "id": "led_color-b595444b",
                "type": "led_color",
                "position": {
                    "x": 1291.0713228246407,
                    "y": 237.43380511744618
                },
                "data": {}
            },
            {
                "id": "greater_than-0682f9fa",
                "type": "greater_than",
                "position": {
                    "x": 440.6492911907536,
                    "y": 152.60651454776536
                },
                "data": {
                    "value": 0,
                    "threshold": 0.5
                }
            },
            {
                "id": "less_than-ac4c3360",
                "type": "less_than",
                "position": {
                    "x": 444.7827655057571,
                    "y": 299.640100895742
                },
                "data": {
                    "value": 0,
                    "threshold": 0.5
                }
            },
            {
                "id": "add-d90b71a3",
                "type": "add",
                "position": {
                    "x": 154.84906712480716,
                    "y": 408.2914257472589
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "subtract-d7f3bd3e",
                "type": "subtract",
                "position": {
                    "x": 154.25857079409235,
                    "y": 239.99997149355062
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "constant-3a6a31b7",
                "type": "constant",
                "position": {
                    "x": -116.77924500398501,
                    "y": 443.13070925943
                },
                "data": {
                    "value": 0.2
                }
            },
            {
                "id": "and_or-29818f0f",
                "type": "and_or",
                "position": {
                    "x": 706.9631363431129,
                    "y": 198.66522834351701
                },
                "data": {
                    "a": 0,
                    "b": 0,
                    "mode": "and"
                }
            },
            {
                "id": "position_x-223d5f3d",
                "type": "position",
                "position": {
                    "x": -136.28917796062834,
                    "y": -177.54104620849802
                },
                "data": {
                    "space": "scene",
                    "axis": "x"
                }
            },
            {
                "id": "multiply-c174e138",
                "type": "multiply",
                "position": {
                    "x": 268.3904688071749,
                    "y": -297.2589941376679
                },
                "data": {
                    "a": 1,
                    "b": -1
                }
            },
            {
                "id": "add-8fdeda67",
                "type": "add",
                "position": {
                    "x": 604.170651129605,
                    "y": -236.4127077436851
                },
                "data": {
                    "a": 0,
                    "b": 1
                }
            },
            {
                "id": "multiply-89c92675",
                "type": "multiply",
                "position": {
                    "x": 251.1133055937624,
                    "y": -131.5857049123779
                },
                "data": {
                    "a": 1,
                    "b": -1
                }
            },
            {
                "id": "constant-40ede49d",
                "type": "constant",
                "position": {
                    "x": -76.78555926256647,
                    "y": 25.235491323257577
                },
                "data": {
                    "value": 1
                }
            },
            {
                "id": "clamp-65d3a4f6",
                "type": "clamp",
                "position": {
                    "x": 508.56842454745276,
                    "y": -44.36963855673039
                },
                "data": {
                    "value": 0,
                    "min": 0,
                    "max": 1
                }
            },
            {
                "id": "scheme_random_color-c0eb7c38",
                "type": "scheme_random_color",
                "position": {
                    "x": 933.937210759846,
                    "y": -58.31865113608944
                },
                "data": {
                    "trigger": 0,
                    "seed": 42
                }
            },
            {
                "id": "brightness-52155604",
                "type": "brightness",
                "position": {
                    "x": 1036.3832414465523,
                    "y": 127.77597341407466
                },
                "data": {
                    "amount": 1
                }
            }
        ],
        "edges": [
            {
                "id": "e-beat_phase-e7a511d3-value-add-d90b71a3-a-kfxiru",
                "source": "beat_phase-e7a511d3",
                "sourceHandle": "value",
                "target": "add-d90b71a3",
                "targetHandle": "a"
            },
            {
                "id": "e-add-d90b71a3-value-less_than-ac4c3360-threshold-hd8ls1",
                "source": "add-d90b71a3",
                "sourceHandle": "value",
                "target": "less_than-ac4c3360",
                "targetHandle": "threshold"
            },
            {
                "id": "e-constant-3a6a31b7-value-add-d90b71a3-b-fxdrg9",
                "source": "constant-3a6a31b7",
                "sourceHandle": "value",
                "target": "add-d90b71a3",
                "targetHandle": "b"
            },
            {
                "id": "e-constant-3a6a31b7-value-subtract-d7f3bd3e-b-e8ie3b",
                "source": "constant-3a6a31b7",
                "sourceHandle": "value",
                "target": "subtract-d7f3bd3e",
                "targetHandle": "b"
            },
            {
                "id": "e-beat_phase-e7a511d3-value-subtract-d7f3bd3e-a-48e7gv",
                "source": "beat_phase-e7a511d3",
                "sourceHandle": "value",
                "target": "subtract-d7f3bd3e",
                "targetHandle": "a"
            },
            {
                "id": "e-subtract-d7f3bd3e-value-greater_than-0682f9fa-threshold-et0rld",
                "source": "subtract-d7f3bd3e",
                "sourceHandle": "value",
                "target": "greater_than-0682f9fa",
                "targetHandle": "threshold"
            },
            {
                "id": "e-less_than-ac4c3360-value-and_or-29818f0f-b-9heovy",
                "source": "less_than-ac4c3360",
                "sourceHandle": "value",
                "target": "and_or-29818f0f",
                "targetHandle": "b"
            },
            {
                "id": "e-greater_than-0682f9fa-value-and_or-29818f0f-a-1u9noh",
                "source": "greater_than-0682f9fa",
                "sourceHandle": "value",
                "target": "and_or-29818f0f",
                "targetHandle": "a"
            },
            {
                "id": "e-position_x-223d5f3d-value-multiply-c174e138-a-4snke5",
                "source": "position_x-223d5f3d",
                "sourceHandle": "value",
                "target": "multiply-c174e138",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-c174e138-value-add-8fdeda67-a-0f121s",
                "source": "multiply-c174e138",
                "sourceHandle": "value",
                "target": "add-8fdeda67",
                "targetHandle": "a"
            },
            {
                "id": "e-add-8fdeda67-value-greater_than-0682f9fa-value-s5sei8",
                "source": "add-8fdeda67",
                "sourceHandle": "value",
                "target": "greater_than-0682f9fa",
                "targetHandle": "value"
            },
            {
                "id": "e-add-8fdeda67-value-less_than-ac4c3360-value-rmykb1",
                "source": "add-8fdeda67",
                "sourceHandle": "value",
                "target": "less_than-ac4c3360",
                "targetHandle": "value"
            },
            {
                "id": "e-multiply-89c92675-value-multiply-c174e138-b-snye00",
                "source": "multiply-89c92675",
                "sourceHandle": "value",
                "target": "multiply-c174e138",
                "targetHandle": "b"
            },
            {
                "id": "e-constant-40ede49d-value-multiply-89c92675-a-mjys8u",
                "source": "constant-40ede49d",
                "sourceHandle": "value",
                "target": "multiply-89c92675",
                "targetHandle": "a"
            },
            {
                "id": "e-constant-40ede49d-value-clamp-65d3a4f6-value-llfssx",
                "source": "constant-40ede49d",
                "sourceHandle": "value",
                "target": "clamp-65d3a4f6",
                "targetHandle": "value"
            },
            {
                "id": "e-clamp-65d3a4f6-value-add-8fdeda67-b-7zdui6",
                "source": "clamp-65d3a4f6",
                "sourceHandle": "value",
                "target": "add-8fdeda67",
                "targetHandle": "b"
            },
            {
                "id": "e-scheme_random_color-c0eb7c38-value-brightness-52155604-color-q0gq0b",
                "source": "scheme_random_color-c0eb7c38",
                "sourceHandle": "value",
                "target": "brightness-52155604",
                "targetHandle": "color"
            },
            {
                "id": "e-and_or-29818f0f-value-brightness-52155604-amount-kug1k3",
                "source": "and_or-29818f0f",
                "sourceHandle": "value",
                "target": "brightness-52155604",
                "targetHandle": "amount"
            },
            {
                "id": "e-brightness-52155604-value-led_color-b595444b-color-wrawi3",
                "source": "brightness-52155604",
                "sourceHandle": "value",
                "target": "led_color-b595444b",
                "targetHandle": "color"
            }
        ]
    },
    exposed_params=[
        {"node_id": "constant-3a6a31b7", "param_key": "value", "label": "Beat Window", "min": 0.0, "max": 1.0, "default": 0.2},
        {"node_id": "position_x-223d5f3d", "param_key": "axis", "label": "Sweep Axis", "options": ["x", "y", "z", "xy", "xz", "yz", "xyz"], "default": "x"},
        {"node_id": "position_x-223d5f3d", "param_key": "space", "label": "Sweep Space", "options": ["scene", "local", "meters"], "default": "scene"},
        {"node_id": "constant-40ede49d", "param_key": "value", "label": "Mirror Amount", "min": -1.0, "max": 1.0, "default": 0.0},
    ],
)


IN_AND_OUT = Effect(
    name="In and Out",
    description=(
        "Position X is folded into a centre-distance parabola, then added to or subtracted from Beat "
        "Phase depending on which half of an 8-beat Counter cycle it is (Greater Than/Not switches "
        "the sign) and thresholded through Square -- so the lit segments sweep toward the centre for "
        "four beats, then away from it for the next four, tinted by one fixed Scheme Random Color "
        "pick."
    ),
    graph={
        "nodes": [
            {
                "id": "led_color-b2557e48",
                "type": "led_color",
                "position": {
                    "x": 2102.2067980382326,
                    "y": 106.93881372889075
                },
                "data": {}
            },
            {
                "id": "beat_phase-ccaeb9a9",
                "type": "beat_phase",
                "position": {
                    "x": -250.5746917907017,
                    "y": 214.87922895264302
                },
                "data": {}
            },
            {
                "id": "counter-4e64f03d",
                "type": "counter",
                "position": {
                    "x": 65.4249377534191,
                    "y": 281.8139811835756
                },
                "data": {
                    "trigger": 0,
                    "reset": 0,
                    "max": 8
                }
            },
            {
                "id": "add-2400514c",
                "type": "add",
                "position": {
                    "x": 249.58140697611185,
                    "y": 514.9539523881058
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "add-f823b312",
                "type": "add",
                "position": {
                    "x": 784.5239585716878,
                    "y": -12.367043298591227
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "square-b6558b2d",
                "type": "square",
                "position": {
                    "x": 1282.653272635856,
                    "y": -173.09520028973196
                },
                "data": {
                    "x": 0,
                    "duty": 0.5
                }
            },
            {
                "id": "greater_than-272a45f3",
                "type": "greater_than",
                "position": {
                    "x": 682.8177525910747,
                    "y": 596.3493929672599
                },
                "data": {
                    "value": 0,
                    "threshold": 4.5
                }
            },
            {
                "id": "subtract-d9c93939",
                "type": "subtract",
                "position": {
                    "x": 423.9185597719462,
                    "y": 716.0509506728522
                },
                "data": {
                    "a": 0,
                    "b": 1
                }
            },
            {
                "id": "not-0c884131",
                "type": "not",
                "position": {
                    "x": 1005.5715300810114,
                    "y": 668.5851547646664
                },
                "data": {
                    "value": 0
                }
            },
            {
                "id": "subtract-e83231a6",
                "type": "subtract",
                "position": {
                    "x": 727.9088823101135,
                    "y": 183.06116373194328
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "multiply-cf0eb3a0",
                "type": "multiply",
                "position": {
                    "x": 1262.848580345762,
                    "y": 231.88371054852382
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            },
            {
                "id": "multiply-a2ef1c34",
                "type": "multiply",
                "position": {
                    "x": 1263.952049534486,
                    "y": 399.98510730295743
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            },
            {
                "id": "add-2f6b7f5f",
                "type": "add",
                "position": {
                    "x": 1585.8170048771758,
                    "y": 323.86435855460775
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "scheme_random_color-e98cf996",
                "type": "scheme_random_color",
                "position": {
                    "x": 1588.7592503779308,
                    "y": -301.9159312338036
                },
                "data": {
                    "trigger": 0,
                    "seed": 32
                }
            },
            {
                "id": "brightness-beba5cd4",
                "type": "brightness",
                "position": {
                    "x": 1897.6186514004166,
                    "y": -79.3012794228471
                },
                "data": {
                    "amount": 1
                }
            },
            {
                "id": "position-c01c8238",
                "type": "position",
                "position": {
                    "x": -99.43066072002281,
                    "y": -440.2074859784965
                },
                "data": {
                    "space": "scene",
                    "axis": "x"
                }
            },
            {
                "id": "add-4c97499e",
                "type": "add",
                "position": {
                    "x": 434.10190830161434,
                    "y": -513.397210190439
                },
                "data": {
                    "a": 0,
                    "b": 1
                }
            },
            {
                "id": "multiply-57547940",
                "type": "multiply",
                "position": {
                    "x": 184.4360266440533,
                    "y": -502.45295236435413
                },
                "data": {
                    "a": 1,
                    "b": -2
                }
            },
            {
                "id": "multiply-646d419c",
                "type": "multiply",
                "position": {
                    "x": 817.8349483287147,
                    "y": -459.4668146919779
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            }
        ],
        "edges": [
            {
                "id": "e-beat_phase-ccaeb9a9-value-counter-4e64f03d-trigger-7vtxqm",
                "source": "beat_phase-ccaeb9a9",
                "sourceHandle": "value",
                "target": "counter-4e64f03d",
                "targetHandle": "trigger"
            },
            {
                "id": "e-beat_phase-ccaeb9a9-value-add-2400514c-a-cvh15v",
                "source": "beat_phase-ccaeb9a9",
                "sourceHandle": "value",
                "target": "add-2400514c",
                "targetHandle": "a"
            },
            {
                "id": "e-counter-4e64f03d-count-add-2400514c-b-zklipl",
                "source": "counter-4e64f03d",
                "sourceHandle": "count",
                "target": "add-2400514c",
                "targetHandle": "b"
            },
            {
                "id": "e-add-2400514c-value-subtract-d9c93939-a-6drxvk",
                "source": "add-2400514c",
                "sourceHandle": "value",
                "target": "subtract-d9c93939",
                "targetHandle": "a"
            },
            {
                "id": "e-subtract-d9c93939-value-greater_than-272a45f3-value-kg4b4r",
                "source": "subtract-d9c93939",
                "sourceHandle": "value",
                "target": "greater_than-272a45f3",
                "targetHandle": "value"
            },
            {
                "id": "e-greater_than-272a45f3-value-not-0c884131-value-tc8uei",
                "source": "greater_than-272a45f3",
                "sourceHandle": "value",
                "target": "not-0c884131",
                "targetHandle": "value"
            },
            {
                "id": "e-subtract-e83231a6-value-multiply-cf0eb3a0-a-2mrxaf",
                "source": "subtract-e83231a6",
                "sourceHandle": "value",
                "target": "multiply-cf0eb3a0",
                "targetHandle": "a"
            },
            {
                "id": "e-greater_than-272a45f3-value-multiply-cf0eb3a0-b-evqnt1",
                "source": "greater_than-272a45f3",
                "sourceHandle": "value",
                "target": "multiply-cf0eb3a0",
                "targetHandle": "b"
            },
            {
                "id": "e-not-0c884131-value-multiply-a2ef1c34-b-67mrci",
                "source": "not-0c884131",
                "sourceHandle": "value",
                "target": "multiply-a2ef1c34",
                "targetHandle": "b"
            },
            {
                "id": "e-add-f823b312-value-multiply-a2ef1c34-a-lpuo04",
                "source": "add-f823b312",
                "sourceHandle": "value",
                "target": "multiply-a2ef1c34",
                "targetHandle": "a"
            },
            {
                "id": "e-beat_phase-ccaeb9a9-value-subtract-e83231a6-b-c9olmx",
                "source": "beat_phase-ccaeb9a9",
                "sourceHandle": "value",
                "target": "subtract-e83231a6",
                "targetHandle": "b"
            },
            {
                "id": "e-beat_phase-ccaeb9a9-value-add-f823b312-b-b227s3",
                "source": "beat_phase-ccaeb9a9",
                "sourceHandle": "value",
                "target": "add-f823b312",
                "targetHandle": "b"
            },
            {
                "id": "e-multiply-cf0eb3a0-value-add-2f6b7f5f-a-fr7xl7",
                "source": "multiply-cf0eb3a0",
                "sourceHandle": "value",
                "target": "add-2f6b7f5f",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-a2ef1c34-value-add-2f6b7f5f-b-ub70cd",
                "source": "multiply-a2ef1c34",
                "sourceHandle": "value",
                "target": "add-2f6b7f5f",
                "targetHandle": "b"
            },
            {
                "id": "e-add-2f6b7f5f-value-square-b6558b2d-x-tfxesu",
                "source": "add-2f6b7f5f",
                "sourceHandle": "value",
                "target": "square-b6558b2d",
                "targetHandle": "x"
            },
            {
                "id": "e-square-b6558b2d-value-brightness-beba5cd4-amount-88o3oc",
                "source": "square-b6558b2d",
                "sourceHandle": "value",
                "target": "brightness-beba5cd4",
                "targetHandle": "amount"
            },
            {
                "id": "e-scheme_random_color-e98cf996-value-brightness-beba5cd4-color-5jjh4h",
                "source": "scheme_random_color-e98cf996",
                "sourceHandle": "value",
                "target": "brightness-beba5cd4",
                "targetHandle": "color"
            },
            {
                "id": "e-brightness-beba5cd4-value-led_color-b2557e48-color-35b3tf",
                "source": "brightness-beba5cd4",
                "sourceHandle": "value",
                "target": "led_color-b2557e48",
                "targetHandle": "color"
            },
            {
                "id": "e-position-c01c8238-value-multiply-57547940-a-gtdr6c",
                "source": "position-c01c8238",
                "sourceHandle": "value",
                "target": "multiply-57547940",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-57547940-value-add-4c97499e-a-gz3gzi",
                "source": "multiply-57547940",
                "sourceHandle": "value",
                "target": "add-4c97499e",
                "targetHandle": "a"
            },
            {
                "id": "e-add-4c97499e-value-multiply-646d419c-a-rtnicz",
                "source": "add-4c97499e",
                "sourceHandle": "value",
                "target": "multiply-646d419c",
                "targetHandle": "a"
            },
            {
                "id": "e-add-4c97499e-value-multiply-646d419c-b-djztu4",
                "source": "add-4c97499e",
                "sourceHandle": "value",
                "target": "multiply-646d419c",
                "targetHandle": "b"
            },
            {
                "id": "e-multiply-646d419c-value-add-f823b312-a-7m8rci",
                "source": "multiply-646d419c",
                "sourceHandle": "value",
                "target": "add-f823b312",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-646d419c-value-subtract-e83231a6-a-8fe54f",
                "source": "multiply-646d419c",
                "sourceHandle": "value",
                "target": "subtract-e83231a6",
                "targetHandle": "a"
            }
        ]
    },
    exposed_params=[
        {"node_id": "position-c01c8238", "param_key": "axis", "label": "Sweep Axis", "options": ["x", "y", "z", "xy", "xz", "yz", "xyz"], "default": "x"},
    ],
)


NOISE_DRIFT = Effect(
    name="Noise Drift",
    description=(
        "A 1-D value-noise field drifts across the strip: Position X (scale exposed) plus an ever- "
        "advancing offset (a Counter incremented once per beat, nudged by Beat Phase x a small "
        "amount) feeds Noise, remapped into brightness and tinted by one fixed Scheme Random Color "
        "pick."
    ),
    graph={
        "nodes": [
            {
                "id": "noise-a07ad5cd",
                "type": "noise",
                "position": {
                    "x": 363,
                    "y": 284.09375
                },
                "data": {
                    "scale": 1,
                    "seed": 0
                }
            },
            {
                "id": "position-84b64585",
                "type": "position",
                "position": {
                    "x": -504.1074872262657,
                    "y": 72.37243215766563
                },
                "data": {
                    "space": "scene",
                    "axis": "x"
                }
            },
            {
                "id": "beat_phase-4e14988c",
                "type": "beat_phase",
                "position": {
                    "x": -837.2356704497718,
                    "y": 444.7629082691316
                },
                "data": {}
            },
            {
                "id": "counter-12ac314c",
                "type": "counter",
                "position": {
                    "x": -539.880614723844,
                    "y": 251.96397402043772
                },
                "data": {
                    "trigger": 0,
                    "reset": 0,
                    "max": 1114
                }
            },
            {
                "id": "scheme_random_color-11d71eb3",
                "type": "scheme_random_color",
                "position": {
                    "x": 710.5966296738711,
                    "y": 77.89388216076753
                },
                "data": {
                    "trigger": 0,
                    "seed": 0
                }
            },
            {
                "id": "brightness-65975ce4",
                "type": "brightness",
                "position": {
                    "x": 875.1763823032193,
                    "y": 330.34248577019105
                },
                "data": {
                    "amount": 1
                }
            },
            {
                "id": "led_color-a7bd90f0",
                "type": "led_color",
                "position": {
                    "x": 1274.7704427126102,
                    "y": 409.14550291898894
                },
                "data": {}
            },
            {
                "id": "multiply-41229d76",
                "type": "multiply",
                "position": {
                    "x": -192.587857558012,
                    "y": 39.243291278724314
                },
                "data": {
                    "a": 1,
                    "b": 1
                }
            },
            {
                "id": "add-01d2497b",
                "type": "add",
                "position": {
                    "x": 137.73848598269421,
                    "y": 176.31038696969074
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "multiply-2858d1fb",
                "type": "multiply",
                "position": {
                    "x": 389.80608092319164,
                    "y": 496.32229368761796
                },
                "data": {
                    "a": 1,
                    "b": 4
                }
            },
            {
                "id": "add-48d1765d",
                "type": "add",
                "position": {
                    "x": 661.1180208667796,
                    "y": 464.70599716302615
                },
                "data": {
                    "a": 0,
                    "b": -2
                }
            },
            {
                "id": "sine-906acfc1",
                "type": "sine",
                "position": {
                    "x": 1354.1766511942217,
                    "y": 691.1669118042869
                },
                "data": {
                    "x": 0
                }
            },
            {
                "id": "multiply-8df68a34",
                "type": "multiply",
                "position": {
                    "x": -255.18287271227214,
                    "y": 467.6161341186304
                },
                "data": {
                    "a": 1,
                    "b": 0.2
                }
            },
            {
                "id": "add-b1259aee",
                "type": "add",
                "position": {
                    "x": 77.36969534381626,
                    "y": 392.59901794506436
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            }
        ],
        "edges": [
            {
                "id": "e-beat_phase-4e14988c-value-counter-12ac314c-trigger-pz466a",
                "source": "beat_phase-4e14988c",
                "sourceHandle": "value",
                "target": "counter-12ac314c",
                "targetHandle": "trigger"
            },
            {
                "id": "e-scheme_random_color-11d71eb3-value-brightness-65975ce4-color-ban33w",
                "source": "scheme_random_color-11d71eb3",
                "sourceHandle": "value",
                "target": "brightness-65975ce4",
                "targetHandle": "color"
            },
            {
                "id": "e-brightness-65975ce4-value-led_color-a7bd90f0-color-3dj3vo",
                "source": "brightness-65975ce4",
                "sourceHandle": "value",
                "target": "led_color-a7bd90f0",
                "targetHandle": "color"
            },
            {
                "id": "e-position-84b64585-value-multiply-41229d76-a-vsol2s",
                "source": "position-84b64585",
                "sourceHandle": "value",
                "target": "multiply-41229d76",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-41229d76-value-add-01d2497b-b-43kl4a",
                "source": "multiply-41229d76",
                "sourceHandle": "value",
                "target": "add-01d2497b",
                "targetHandle": "b"
            },
            {
                "id": "e-add-01d2497b-value-noise-a07ad5cd-x-3r2pqw",
                "source": "add-01d2497b",
                "sourceHandle": "value",
                "target": "noise-a07ad5cd",
                "targetHandle": "x"
            },
            {
                "id": "e-noise-a07ad5cd-value-multiply-2858d1fb-a-2gq7rd",
                "source": "noise-a07ad5cd",
                "sourceHandle": "value",
                "target": "multiply-2858d1fb",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-2858d1fb-value-add-48d1765d-a-hsajau",
                "source": "multiply-2858d1fb",
                "sourceHandle": "value",
                "target": "add-48d1765d",
                "targetHandle": "a"
            },
            {
                "id": "e-add-48d1765d-value-brightness-65975ce4-amount-t1zn5i",
                "source": "add-48d1765d",
                "sourceHandle": "value",
                "target": "brightness-65975ce4",
                "targetHandle": "amount"
            },
            {
                "id": "e-beat_phase-4e14988c-value-multiply-8df68a34-a-5fo8l3",
                "source": "beat_phase-4e14988c",
                "sourceHandle": "value",
                "target": "multiply-8df68a34",
                "targetHandle": "a"
            },
            {
                "id": "e-multiply-8df68a34-value-add-b1259aee-b-nzlg8h",
                "source": "multiply-8df68a34",
                "sourceHandle": "value",
                "target": "add-b1259aee",
                "targetHandle": "b"
            },
            {
                "id": "e-add-b1259aee-value-add-01d2497b-a-52pvle",
                "source": "add-b1259aee",
                "sourceHandle": "value",
                "target": "add-01d2497b",
                "targetHandle": "a"
            },
            {
                "id": "e-counter-12ac314c-count-add-b1259aee-a-dhu0d9",
                "source": "counter-12ac314c",
                "sourceHandle": "count",
                "target": "add-b1259aee",
                "targetHandle": "a"
            }
        ]
    },
    exposed_params=[
        {"node_id": "multiply-41229d76", "param_key": "b", "label": "Noise Scale", "min": 0.0, "max": 4.0, "default": 3.0},
    ],
)


HALOGEN_BLINDER = Effect(
    name="Halogen Blinder",
    description=(
        "A halogen-blinder-style hit that steps round-robin across the fixtures on the beat: Beat "
        "Phase gates a Counter (max wired to Fixture Index's count, one advance per beat) whose count "
        "is matched (Subtract -> Abs -> Less Than) against this fixture's index -- only the matching "
        "fixture retriggers the Envelope (fast attack, exponential decay). The same Envelope value "
        "drives Brightness and, remapped into a falling Kelvin value, cools Color Temperature from "
        "~2800K toward ~1200K as the flash dies out, mimicking a filament cooling rather than just "
        "dimming."
    ),
    graph={
        "nodes": [
            {
                "id": "beat_phase-ab55f2cb",
                "type": "beat_phase",
                "position": {
                    "x": 239.5,
                    "y": 383.09375
                },
                "data": {}
            },
            {
                "id": "envelope-9cb9e497",
                "type": "envelope",
                "position": {
                    "x": 1988.226723530717,
                    "y": 506.3854710926547
                },
                "data": {
                    "trigger": 0,
                    "attack": 0.01,
                    "hold": 0,
                    "decay": 0.5,
                    "curve": "exponential"
                }
            },
            {
                "id": "fixture_index-e643739c",
                "type": "fixture_index",
                "position": {
                    "x": 803.7784036285634,
                    "y": 68.04123499995967
                },
                "data": {
                    "axis": "y",
                    "reverse": "false"
                }
            },
            {
                "id": "brightness-53e3c62d",
                "type": "brightness",
                "position": {
                    "x": 2584.073700258956,
                    "y": 105.23507530185151
                },
                "data": {
                    "amount": 1
                }
            },
            {
                "id": "color_temperature-21e7b355",
                "type": "color_temperature",
                "position": {
                    "x": 2281.051680690979,
                    "y": -98.18015425546545
                },
                "data": {
                    "kelvin": 2800
                }
            },
            {
                "id": "less_than-7a95d8f5",
                "type": "less_than",
                "position": {
                    "x": 596.1619453636314,
                    "y": 366.845001083786
                },
                "data": {
                    "value": 0,
                    "threshold": 0.05
                }
            },
            {
                "id": "led_color-fe324385",
                "type": "led_color",
                "position": {
                    "x": 2952.2031472766794,
                    "y": 519.2775714613606
                },
                "data": {}
            },
            {
                "id": "counter-dc1d83bd",
                "type": "counter",
                "position": {
                    "x": 898.5006746477221,
                    "y": 401.42706381312587
                },
                "data": {
                    "trigger": 0,
                    "reset": 0,
                    "max": 4
                }
            },
            {
                "id": "subtract-effe7309",
                "type": "subtract",
                "position": {
                    "x": 1233.643059147922,
                    "y": 360.6624557536525
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "add-6314f22a",
                "type": "add",
                "position": {
                    "x": 1142.2574369150389,
                    "y": 114.81087027757775
                },
                "data": {
                    "a": 0,
                    "b": 1
                }
            },
            {
                "id": "abs-99254d74",
                "type": "abs",
                "position": {
                    "x": 1494.0516463956062,
                    "y": 342.87056469946276
                },
                "data": {
                    "value": 0
                }
            },
            {
                "id": "less_than-4282b371",
                "type": "less_than",
                "position": {
                    "x": 1764.973623811676,
                    "y": 321.56073155046755
                },
                "data": {
                    "value": 0,
                    "threshold": 0.5
                }
            },
            {
                "id": "remap-b7f3e983",
                "type": "remap",
                "position": {
                    "x": 1957.8804450136822,
                    "y": -145.8001004348273
                },
                "data": {
                    "value": 0,
                    "in_min": 0,
                    "in_max": 1,
                    "out_min": 1200,
                    "out_max": 2800
                }
            }
        ],
        "edges": [
            {
                "id": "e-color_temperature-21e7b355-value-brightness-53e3c62d-color-kkc63t",
                "source": "color_temperature-21e7b355",
                "sourceHandle": "value",
                "target": "brightness-53e3c62d",
                "targetHandle": "color"
            },
            {
                "id": "e-envelope-9cb9e497-value-brightness-53e3c62d-amount-rfzqix",
                "source": "envelope-9cb9e497",
                "sourceHandle": "value",
                "target": "brightness-53e3c62d",
                "targetHandle": "amount"
            },
            {
                "id": "e-beat_phase-ab55f2cb-value-less_than-7a95d8f5-value-2i04ib",
                "source": "beat_phase-ab55f2cb",
                "sourceHandle": "value",
                "target": "less_than-7a95d8f5",
                "targetHandle": "value"
            },
            {
                "id": "e-less_than-7a95d8f5-value-counter-dc1d83bd-trigger-gqbokj",
                "source": "less_than-7a95d8f5",
                "sourceHandle": "value",
                "target": "counter-dc1d83bd",
                "targetHandle": "trigger"
            },
            {
                "id": "e-fixture_index-e643739c-index-add-6314f22a-a-ri68dk",
                "source": "fixture_index-e643739c",
                "sourceHandle": "index",
                "target": "add-6314f22a",
                "targetHandle": "a"
            },
            {
                "id": "e-counter-dc1d83bd-count-subtract-effe7309-a-zpc8pp",
                "source": "counter-dc1d83bd",
                "sourceHandle": "count",
                "target": "subtract-effe7309",
                "targetHandle": "a"
            },
            {
                "id": "e-add-6314f22a-value-subtract-effe7309-b-znliic",
                "source": "add-6314f22a",
                "sourceHandle": "value",
                "target": "subtract-effe7309",
                "targetHandle": "b"
            },
            {
                "id": "e-subtract-effe7309-value-abs-99254d74-value-d0pkx0",
                "source": "subtract-effe7309",
                "sourceHandle": "value",
                "target": "abs-99254d74",
                "targetHandle": "value"
            },
            {
                "id": "e-abs-99254d74-value-less_than-4282b371-value-tmguif",
                "source": "abs-99254d74",
                "sourceHandle": "value",
                "target": "less_than-4282b371",
                "targetHandle": "value"
            },
            {
                "id": "e-less_than-4282b371-value-envelope-9cb9e497-trigger-vkpnlg",
                "source": "less_than-4282b371",
                "sourceHandle": "value",
                "target": "envelope-9cb9e497",
                "targetHandle": "trigger"
            },
            {
                "id": "e-envelope-9cb9e497-value-remap-b7f3e983-value-nhc0yb",
                "source": "envelope-9cb9e497",
                "sourceHandle": "value",
                "target": "remap-b7f3e983",
                "targetHandle": "value"
            },
            {
                "id": "e-remap-b7f3e983-value-color_temperature-21e7b355-kelvin-shalt2",
                "source": "remap-b7f3e983",
                "sourceHandle": "value",
                "target": "color_temperature-21e7b355",
                "targetHandle": "kelvin"
            },
            {
                "id": "e-fixture_index-e643739c-count-counter-dc1d83bd-max-trdq1n",
                "source": "fixture_index-e643739c",
                "sourceHandle": "count",
                "target": "counter-dc1d83bd",
                "targetHandle": "max"
            },
            {
                "id": "e-brightness-53e3c62d-value-led_color-fe324385-color-olirtl",
                "source": "brightness-53e3c62d",
                "sourceHandle": "value",
                "target": "led_color-fe324385",
                "targetHandle": "color"
            }
        ]
    },
    exposed_params=[
        {"node_id": "envelope-9cb9e497", "param_key": "attack", "label": "Attack (s)", "min": 0.0, "max": 5.0, "default": 0.01},
        {"node_id": "envelope-9cb9e497", "param_key": "hold", "label": "Hold (s)", "min": 0.0, "max": 5.0, "default": 0.0},
        {"node_id": "envelope-9cb9e497", "param_key": "decay", "label": "Decay (s)", "min": 0.01, "max": 10.0, "default": 0.5},
        {"node_id": "less_than-4282b371", "param_key": "threshold", "label": "Match Tolerance", "min": 0.0, "max": 1.0, "default": 0.5},
        {"node_id": "remap-b7f3e983", "param_key": "out_min", "label": "Cool Temp (K)", "min": 0.0, "max": 12000.0, "default": 1200.0},
        {"node_id": "remap-b7f3e983", "param_key": "out_max", "label": "Hot Temp (K)", "min": 0.0, "max": 12000.0, "default": 2800.0},
        {"node_id": "add-6314f22a", "param_key": "b", "label": "Fixture Offset", "min": 0.0, "max": 1.0, "default": 1.0},
    ],
)


HALOGEN_BLINDER_WASH = Effect(
    name="Halogen Blinder Wash",
    description=(
        "Halogen Blinder, plus a dim, ever-present Scheme Random Color wash mixed underneath the "
        "flash (Mix Color between the blinder output and a low-brightness scheme swatch) so the room "
        "never goes fully black between hits."
    ),
    graph={
        "nodes": [
            {
                "id": "beat_phase-ab55f2cb",
                "type": "beat_phase",
                "position": {
                    "x": 239.5,
                    "y": 383.09375
                },
                "data": {}
            },
            {
                "id": "envelope-9cb9e497",
                "type": "envelope",
                "position": {
                    "x": 1988.226723530717,
                    "y": 506.3854710926547
                },
                "data": {
                    "trigger": 0,
                    "attack": 0.01,
                    "hold": 0,
                    "decay": 0.5,
                    "curve": "exponential"
                }
            },
            {
                "id": "fixture_index-e643739c",
                "type": "fixture_index",
                "position": {
                    "x": 803.7784036285634,
                    "y": 68.04123499995967
                },
                "data": {
                    "axis": "y",
                    "reverse": "false"
                }
            },
            {
                "id": "brightness-53e3c62d",
                "type": "brightness",
                "position": {
                    "x": 2584.073700258956,
                    "y": 105.23507530185151
                },
                "data": {
                    "amount": 1
                }
            },
            {
                "id": "color_temperature-21e7b355",
                "type": "color_temperature",
                "position": {
                    "x": 2281.051680690979,
                    "y": -98.18015425546545
                },
                "data": {
                    "kelvin": 2800
                }
            },
            {
                "id": "less_than-7a95d8f5",
                "type": "less_than",
                "position": {
                    "x": 596.1619453636314,
                    "y": 366.845001083786
                },
                "data": {
                    "value": 0,
                    "threshold": 0.05
                }
            },
            {
                "id": "led_color-fe324385",
                "type": "led_color",
                "position": {
                    "x": 2952.2031472766794,
                    "y": 519.2775714613606
                },
                "data": {}
            },
            {
                "id": "counter-dc1d83bd",
                "type": "counter",
                "position": {
                    "x": 898.5006746477221,
                    "y": 401.42706381312587
                },
                "data": {
                    "trigger": 0,
                    "reset": 0,
                    "max": 4
                }
            },
            {
                "id": "subtract-effe7309",
                "type": "subtract",
                "position": {
                    "x": 1233.643059147922,
                    "y": 360.6624557536525
                },
                "data": {
                    "a": 0,
                    "b": 0
                }
            },
            {
                "id": "add-6314f22a",
                "type": "add",
                "position": {
                    "x": 1142.2574369150389,
                    "y": 114.81087027757775
                },
                "data": {
                    "a": 0,
                    "b": 1
                }
            },
            {
                "id": "abs-99254d74",
                "type": "abs",
                "position": {
                    "x": 1494.0516463956062,
                    "y": 342.87056469946276
                },
                "data": {
                    "value": 0
                }
            },
            {
                "id": "less_than-4282b371",
                "type": "less_than",
                "position": {
                    "x": 1764.973623811676,
                    "y": 321.56073155046755
                },
                "data": {
                    "value": 0,
                    "threshold": 0.5
                }
            },
            {
                "id": "remap-b7f3e983",
                "type": "remap",
                "position": {
                    "x": 1957.8804450136822,
                    "y": -145.8001004348273
                },
                "data": {
                    "value": 0,
                    "in_min": 0,
                    "in_max": 1,
                    "out_min": 1200,
                    "out_max": 2800
                }
            },
            {
                "id": "scheme_random_color-5439ec07",
                "type": "scheme_random_color",
                "position": {
                    "x": 1321.1151059397764,
                    "y": 931.4062743590886
                },
                "data": {
                    "trigger": 0,
                    "seed": 0
                }
            },
            {
                "id": "mix_color-a3f7cd08",
                "type": "mix_color",
                "position": {
                    "x": 2627.599087517736,
                    "y": 747.271236019887
                },
                "data": {
                    "t": 0.5
                }
            },
            {
                "id": "brightness-09f0d825",
                "type": "brightness",
                "position": {
                    "x": 1704.887011469733,
                    "y": 973.3236054408028
                },
                "data": {
                    "amount": 0.03
                }
            }
        ],
        "edges": [
            {
                "id": "e-color_temperature-21e7b355-value-brightness-53e3c62d-color-kkc63t",
                "source": "color_temperature-21e7b355",
                "sourceHandle": "value",
                "target": "brightness-53e3c62d",
                "targetHandle": "color"
            },
            {
                "id": "e-envelope-9cb9e497-value-brightness-53e3c62d-amount-rfzqix",
                "source": "envelope-9cb9e497",
                "sourceHandle": "value",
                "target": "brightness-53e3c62d",
                "targetHandle": "amount"
            },
            {
                "id": "e-beat_phase-ab55f2cb-value-less_than-7a95d8f5-value-2i04ib",
                "source": "beat_phase-ab55f2cb",
                "sourceHandle": "value",
                "target": "less_than-7a95d8f5",
                "targetHandle": "value"
            },
            {
                "id": "e-less_than-7a95d8f5-value-counter-dc1d83bd-trigger-gqbokj",
                "source": "less_than-7a95d8f5",
                "sourceHandle": "value",
                "target": "counter-dc1d83bd",
                "targetHandle": "trigger"
            },
            {
                "id": "e-fixture_index-e643739c-index-add-6314f22a-a-ri68dk",
                "source": "fixture_index-e643739c",
                "sourceHandle": "index",
                "target": "add-6314f22a",
                "targetHandle": "a"
            },
            {
                "id": "e-counter-dc1d83bd-count-subtract-effe7309-a-zpc8pp",
                "source": "counter-dc1d83bd",
                "sourceHandle": "count",
                "target": "subtract-effe7309",
                "targetHandle": "a"
            },
            {
                "id": "e-add-6314f22a-value-subtract-effe7309-b-znliic",
                "source": "add-6314f22a",
                "sourceHandle": "value",
                "target": "subtract-effe7309",
                "targetHandle": "b"
            },
            {
                "id": "e-subtract-effe7309-value-abs-99254d74-value-d0pkx0",
                "source": "subtract-effe7309",
                "sourceHandle": "value",
                "target": "abs-99254d74",
                "targetHandle": "value"
            },
            {
                "id": "e-abs-99254d74-value-less_than-4282b371-value-tmguif",
                "source": "abs-99254d74",
                "sourceHandle": "value",
                "target": "less_than-4282b371",
                "targetHandle": "value"
            },
            {
                "id": "e-less_than-4282b371-value-envelope-9cb9e497-trigger-vkpnlg",
                "source": "less_than-4282b371",
                "sourceHandle": "value",
                "target": "envelope-9cb9e497",
                "targetHandle": "trigger"
            },
            {
                "id": "e-envelope-9cb9e497-value-remap-b7f3e983-value-nhc0yb",
                "source": "envelope-9cb9e497",
                "sourceHandle": "value",
                "target": "remap-b7f3e983",
                "targetHandle": "value"
            },
            {
                "id": "e-remap-b7f3e983-value-color_temperature-21e7b355-kelvin-shalt2",
                "source": "remap-b7f3e983",
                "sourceHandle": "value",
                "target": "color_temperature-21e7b355",
                "targetHandle": "kelvin"
            },
            {
                "id": "e-fixture_index-e643739c-count-counter-dc1d83bd-max-trdq1n",
                "source": "fixture_index-e643739c",
                "sourceHandle": "count",
                "target": "counter-dc1d83bd",
                "targetHandle": "max"
            },
            {
                "id": "e-brightness-53e3c62d-value-mix_color-a3f7cd08-a-qforru",
                "source": "brightness-53e3c62d",
                "sourceHandle": "value",
                "target": "mix_color-a3f7cd08",
                "targetHandle": "a"
            },
            {
                "id": "e-mix_color-a3f7cd08-value-led_color-fe324385-color-huxbyq",
                "source": "mix_color-a3f7cd08",
                "sourceHandle": "value",
                "target": "led_color-fe324385",
                "targetHandle": "color"
            },
            {
                "id": "e-scheme_random_color-5439ec07-value-brightness-09f0d825-color-9imcb5",
                "source": "scheme_random_color-5439ec07",
                "sourceHandle": "value",
                "target": "brightness-09f0d825",
                "targetHandle": "color"
            },
            {
                "id": "e-brightness-09f0d825-value-mix_color-a3f7cd08-b-mkngab",
                "source": "brightness-09f0d825",
                "sourceHandle": "value",
                "target": "mix_color-a3f7cd08",
                "targetHandle": "b"
            }
        ]
    },
    exposed_params=[
        {"node_id": "brightness-09f0d825", "param_key": "amount", "label": "Background Brightness", "min": 0.0, "max": 1.0, "default": 0.03},
        {"node_id": "envelope-9cb9e497", "param_key": "attack", "label": "Attack (s)", "min": 0.0, "max": 5.0, "default": 0.01},
        {"node_id": "envelope-9cb9e497", "param_key": "hold", "label": "Hold (s)", "min": 0.0, "max": 5.0, "default": 0.0},
        {"node_id": "envelope-9cb9e497", "param_key": "decay", "label": "Decay (s)", "min": 0.01, "max": 10.0, "default": 0.5},
        {"node_id": "less_than-4282b371", "param_key": "threshold", "label": "Match Tolerance", "min": 0.0, "max": 1.0, "default": 0.5},
        {"node_id": "remap-b7f3e983", "param_key": "out_min", "label": "Cool Temp (K)", "min": 0.0, "max": 12000.0, "default": 1200.0},
        {"node_id": "remap-b7f3e983", "param_key": "out_max", "label": "Hot Temp (K)", "min": 0.0, "max": 12000.0, "default": 2800.0},
        {"node_id": "add-6314f22a", "param_key": "b", "label": "Fixture Offset", "min": 0.0, "max": 1.0, "default": 1.0},
    ],
)

EXAMPLE_EFFECTS: list[Effect] = [
    BEAT_BAR,
    BASS_PULSE_RAINBOW,
    SCANNER,
    RIPPLE,
    TWINKLE,
    STROBE_DROP,
    PLASMA,
    BEAT_WIPE,
    ZONE_CHASE,
    PHRASE_RISER,
    BEAT_BOUNCE,
    CORE_SHOCKWAVE,
    BASS_BLOOM,
    RING_SLAMMER,
    RANDOM_STROBE,
    SIDE_PHASE,
    IN_AND_OUT,
    NOISE_DRIFT,
    HALOGEN_BLINDER,
    HALOGEN_BLINDER_WASH,
]


def seed_example_effects(session: Session) -> list[Effect]:
    """Creates each example effect that isn't already present (matched by
    name). Returns the ones actually created."""
    existing_names = set(session.exec(select(Effect.name)).all())
    created = []
    for template in EXAMPLE_EFFECTS:
        if template.name in existing_names:
            continue
        effect = Effect(
            name=template.name,
            description=template.description,
            graph=template.graph,
            exposed_params=template.exposed_params,
        )
        session.add(effect)
        created.append(effect)
    session.commit()
    for effect in created:
        session.refresh(effect)
    return created


if __name__ == "__main__":
    init_db()
    with Session(engine) as session:
        created = seed_example_effects(session)
    if created:
        print(f"Created {len(created)} example effect(s):")
        for effect in created:
            print(f"  - {effect.name} (id={effect.id})")
    else:
        print("All example effects already exist, nothing to do.")
