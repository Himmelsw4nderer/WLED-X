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
