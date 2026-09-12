import asyncio

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from wled_x import db
from wled_x.api.schemas import ConsoleState
from wled_x.effects import engine as engine_module
from wled_x.effects.engine import RenderLoop
from wled_x.models.audio_source import AudioSourceConfig
from wled_x.models.effect import Effect


class _FakeCapture:
    """Stands in for AudioCapture so reconfigure_audio_sources's bookkeeping
    (which source is running, which capture backs it) can be tested without
    touching real audio hardware."""

    def __init__(self, device: str | None = None, mode: str = "loopback") -> None:
        self.device = device
        self.mode = mode
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    async def get(self):
        await asyncio.Event().wait()  # never resolves; cancellation is what ends it


@pytest.fixture
def audio_db(monkeypatch):
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "engine", eng)
    monkeypatch.setattr(engine_module, "AudioCapture", _FakeCapture)
    return eng


async def test_reconfigure_audio_sources_starts_and_stops_by_enabled_flag(audio_db):
    with Session(audio_db) as session:
        session.add(AudioSourceConfig(name="desktop", enabled=True, mode="loopback", device=None))
        session.add(AudioSourceConfig(name="mic", enabled=False, mode="input", device=None))
        session.commit()

    loop = RenderLoop()
    loop._running = True
    try:
        await loop.reconfigure_audio_sources()
        assert "desktop" in loop._drain_tasks
        assert "mic" not in loop._drain_tasks
        assert loop._sources["desktop"].capture.started is True

        with Session(audio_db) as session:
            row = session.get(AudioSourceConfig, "mic")
            row.enabled = True
            session.add(row)
            session.commit()
        await loop.reconfigure_audio_sources()
        assert "mic" in loop._drain_tasks
        assert loop._sources["mic"].capture.started is True
    finally:
        for name in list(loop._drain_tasks):
            await loop._stop_source(name)


async def test_reconfigure_audio_sources_swaps_capture_when_device_changes(audio_db):
    with Session(audio_db) as session:
        session.add(AudioSourceConfig(name="desktop", enabled=True, mode="loopback", device=None))
        session.add(AudioSourceConfig(name="mic", enabled=False, mode="input", device=None))
        session.commit()

    loop = RenderLoop()
    loop._running = True
    try:
        await loop.reconfigure_audio_sources()
        old_capture = loop._sources["desktop"].capture

        with Session(audio_db) as session:
            row = session.get(AudioSourceConfig, "desktop")
            row.device = "custom_sink.monitor"
            session.add(row)
            session.commit()
        await loop.reconfigure_audio_sources()

        new_capture = loop._sources["desktop"].capture
        assert old_capture.stopped is True
        assert new_capture is not old_capture
        assert new_capture.device == "custom_sink.monitor"
        assert new_capture.started is True
    finally:
        for name in list(loop._drain_tasks):
            await loop._stop_source(name)


def test_two_instances_of_the_same_node_type_are_overridden_independently():
    # Regression test: the console override key used to be "{effect_id}:{param_key}",
    # so two nodes exposing a param with the same name (e.g. two Constant nodes both
    # exposing "value") collided onto the same override -- moving one console slider
    # silently moved both. Key now includes node_id.
    effect = Effect(
        id=1,
        name="two constants",
        graph={"nodes": [], "edges": []},
        exposed_params=[
            {"node_id": "c1", "param_key": "value", "label": "A", "min": 0, "max": 1, "default": 0},
            {"node_id": "c2", "param_key": "value", "label": "B", "min": 0, "max": 1, "default": 0},
        ],
    )
    console_state = ConsoleState(param_overrides={"1:c1:value": 0.2, "1:c2:value": 0.8})

    loop = RenderLoop()
    overrides = loop._resolve_param_overrides(effect, {"params": {}}, console_state)

    assert overrides[("c1", "value")] == 0.2
    assert overrides[("c2", "value")] == 0.8


def test_scene_stored_params_feed_the_fader_bank_when_no_live_override():
    # Fader-bank values persist on the scene (Scene.assignments[].params),
    # keyed "{node_id}:{param_key}". With nothing being ridden live, the
    # engine picks them up; a live console override still wins over them.
    effect = Effect(
        id=7,
        name="wipe",
        graph={"nodes": [], "edges": []},
        exposed_params=[
            {"node_id": "spd", "param_key": "value", "label": "Speed", "min": 0, "max": 1, "default": 0},
            {"node_id": "ax", "param_key": "axis", "label": "Axis", "default": "x", "options": ["x", "y"]},
        ],
    )
    assignment = {"params": {"spd:value": 0.4, "ax:axis": "y"}}
    loop = RenderLoop()

    resolved = loop._resolve_param_overrides(effect, assignment, ConsoleState())
    assert resolved == {("spd", "value"): 0.4, ("ax", "axis"): "y"}

    live = ConsoleState(param_overrides={"7:spd:value": 0.9})
    resolved = loop._resolve_param_overrides(effect, assignment, live)
    assert resolved[("spd", "value")] == 0.9
    assert resolved[("ax", "axis")] == "y"


def test_legacy_scene_params_keyed_by_bare_param_key_still_resolve():
    effect = Effect(
        id=1,
        name="old",
        graph={"nodes": [], "edges": []},
        exposed_params=[
            {"node_id": "n", "param_key": "speed", "label": "Speed", "min": 0, "max": 1, "default": 0},
        ],
    )
    resolved = RenderLoop()._resolve_param_overrides(
        effect, {"params": {"speed": 0.6}}, ConsoleState()
    )
    assert resolved == {("n", "speed"): 0.6}
