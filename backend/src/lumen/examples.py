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


EXAMPLE_EFFECTS: list[Effect] = [BEAT_BAR, BASS_PULSE_RAINBOW]


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
