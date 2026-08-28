"""A handful of ready-made effect graphs, seeded straight into the DB so
there's something to look at (and copy from) besides an empty node canvas.
Each one is deliberately built from small composable nodes rather than one
big bespoke node, matching how the rest of the effect graph is meant to be
used -- see `lumen.effects.nodes` for what each node type does.

Run with `python -m lumen.examples` from the backend dir (with the venv
active). Safe to re-run: effects are matched and skipped by name, never
duplicated or overwritten.
"""

from sqlmodel import Session, select

from lumen.db import engine, init_db
from lumen.models.effect import Effect

# Beats-to-N counter: an 8-beat bar that refills across the strip and wraps.
# Demonstrates the Counter node (counts Beat pulses, wraps at `max`) driving
# a spatial cutoff via Less Than, recolored per-LED with a rainbow HSV sweep.
BEAT_BAR = Effect(
    name="Beat Bar (Counter Demo)",
    description=(
        "An 8-beat bar that fills across the strip one beat at a time, then wraps back to "
        "empty and starts again -- built from Beat -> Counter -> Less Than -> HSV."
    ),
    graph={
        "nodes": [
            {
                "id": "beat1",
                "type": "beat",
                "data": {"decay": 0.4, "source": "desktop"},
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
                "id": "e1",
                "source": "beat1",
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
            "node_id": "beat1",
            "param_key": "decay",
            "label": "Beat Decay",
            "min": 0.05,
            "max": 2.0,
            "default": 0.4,
        },
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

# A slow rainbow hue sweep, pulsed bright on every bass hit. Demonstrates
# Bass Hit (the kick-focused onset track, as distinct from the general Beat
# node) driving brightness while Time drives hue.
BASS_PULSE_RAINBOW = Effect(
    name="Bass Pulse Rainbow",
    description=(
        "A slowly rotating rainbow that flashes bright on every bass/kick hit and fades "
        "between them -- Bass Hit -> HSV's V, Time -> HSV's H."
    ),
    graph={
        "nodes": [
            {"id": "time1", "type": "time", "data": {"speed": 0.07}, "position": {"x": 0, "y": 0}},
            {
                "id": "bass1",
                "type": "bass_hit",
                "data": {"decay": 0.5, "source": "desktop"},
                "position": {"x": 0, "y": 140},
            },
            {"id": "hsv1", "type": "hsv", "data": {"s": 1.0}, "position": {"x": 240, "y": 60}},
            {"id": "out1", "type": "led_color", "data": {}, "position": {"x": 460, "y": 60}},
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
                "source": "bass1",
                "sourceHandle": "value",
                "target": "hsv1",
                "targetHandle": "v",
            },
            {
                "id": "e3",
                "source": "hsv1",
                "sourceHandle": "value",
                "target": "out1",
                "targetHandle": "color",
            },
        ],
    },
    exposed_params=[
        {
            "node_id": "bass1",
            "param_key": "decay",
            "label": "Pulse Decay",
            "min": 0.05,
            "max": 2.0,
            "default": 0.5,
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

# Splits the strip in half and drives each half's brightness from a
# different audio source -- desktop mix on the left (blue), a microphone on
# the right (orange) -- running fully in parallel every frame. Requires
# LUMEN_AUDIO_MIC_ENABLED=true to actually see two different signals; with
# it off, "mic" quietly falls back to reading the desktop source too (see
# lumen.effects.nodes.audio_nodes._source_frame), so this still renders, it
# just won't look different from a single-source effect.
DESKTOP_MIC_SPLIT = Effect(
    name="Desktop + Mic Split",
    description=(
        "Left half of the strip pulses blue with desktop audio, right half pulses orange "
        "with a live mic -- two Audio Level nodes with different Source params, read in "
        "parallel. Set LUMEN_AUDIO_MIC_ENABLED=true to hear the split."
    ),
    graph={
        "nodes": [
            {"id": "idx1", "type": "index_normalized", "data": {}, "position": {"x": 0, "y": 0}},
            {
                "id": "mask1",
                "type": "less_than",
                "data": {"threshold": 0.5},
                "position": {"x": 220, "y": -80},
            },
            {"id": "invmask1", "type": "invert", "data": {}, "position": {"x": 440, "y": -80}},
            {
                "id": "lvl_desktop",
                "type": "audio_level",
                "data": {"source": "desktop"},
                "position": {"x": 0, "y": 120},
            },
            {
                "id": "lvl_mic",
                "type": "audio_level",
                "data": {"source": "mic"},
                "position": {"x": 0, "y": 240},
            },
            {"id": "mul1", "type": "multiply", "data": {}, "position": {"x": 440, "y": 60}},
            {"id": "mul2", "type": "multiply", "data": {}, "position": {"x": 440, "y": 200}},
            {"id": "add1", "type": "add", "data": {}, "position": {"x": 660, "y": 130}},
            {
                "id": "ramp1",
                "type": "color_ramp",
                "data": {
                    "stops": [
                        {"pos": 0.0, "color": [0.15, 0.35, 1.0]},
                        {"pos": 0.499, "color": [0.15, 0.35, 1.0]},
                        {"pos": 0.5, "color": [1.0, 0.45, 0.05]},
                        {"pos": 1.0, "color": [1.0, 0.45, 0.05]},
                    ]
                },
                "position": {"x": 220, "y": 340},
            },
            {"id": "mix1", "type": "mix_color", "data": {}, "position": {"x": 880, "y": 200}},
            {"id": "out1", "type": "led_color", "data": {}, "position": {"x": 1100, "y": 200}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "idx1",
                "sourceHandle": "value",
                "target": "mask1",
                "targetHandle": "value",
            },
            {
                "id": "e2",
                "source": "mask1",
                "sourceHandle": "value",
                "target": "invmask1",
                "targetHandle": "value",
            },
            {
                "id": "e3",
                "source": "mask1",
                "sourceHandle": "value",
                "target": "mul1",
                "targetHandle": "a",
            },
            {
                "id": "e4",
                "source": "lvl_desktop",
                "sourceHandle": "value",
                "target": "mul1",
                "targetHandle": "b",
            },
            {
                "id": "e5",
                "source": "invmask1",
                "sourceHandle": "value",
                "target": "mul2",
                "targetHandle": "a",
            },
            {
                "id": "e6",
                "source": "lvl_mic",
                "sourceHandle": "value",
                "target": "mul2",
                "targetHandle": "b",
            },
            {
                "id": "e7",
                "source": "mul1",
                "sourceHandle": "value",
                "target": "add1",
                "targetHandle": "a",
            },
            {
                "id": "e8",
                "source": "mul2",
                "sourceHandle": "value",
                "target": "add1",
                "targetHandle": "b",
            },
            {
                "id": "e9",
                "source": "idx1",
                "sourceHandle": "value",
                "target": "ramp1",
                "targetHandle": "position",
            },
            {
                "id": "e10",
                "source": "ramp1",
                "sourceHandle": "value",
                "target": "mix1",
                "targetHandle": "b",
            },
            {
                "id": "e11",
                "source": "add1",
                "sourceHandle": "value",
                "target": "mix1",
                "targetHandle": "t",
            },
            {
                "id": "e12",
                "source": "mix1",
                "sourceHandle": "value",
                "target": "out1",
                "targetHandle": "color",
            },
        ],
    },
    exposed_params=[
        {
            "node_id": "mask1",
            "param_key": "threshold",
            "label": "Split Position",
            "min": 0.0,
            "max": 1.0,
            "default": 0.5,
        },
    ],
)


EXAMPLE_EFFECTS: list[Effect] = [BEAT_BAR, BASS_PULSE_RAINBOW, DESKTOP_MIC_SPLIT]


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
