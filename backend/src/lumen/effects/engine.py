"""The render loop: each tick, evaluates the active scene's effect graphs per
fixture, assembles per-device pixel buffers, pushes them to `device_manager`,
and broadcasts a preview frame (plus a periodic audio meter) over the live WS.

Exposed as `render_loop()` / `start_render_loop()` / `stop_render_loop()`;
wiring this into `main.py`'s startup is a later integration step, done
elsewhere to avoid clashing with concurrent edits to that file.
"""

import asyncio
import contextlib
import logging
import time
from typing import Any

import numpy as np
from sqlmodel import Session, select

from lumen.api.schemas import ConsoleState
from lumen.api.ws import manager
from lumen.audio.analysis import NUM_BANDS, AudioAnalyzer, AudioFrame
from lumen.audio.capture import AudioCapture
from lumen.config import settings
from lumen.console.state import console
from lumen.db import engine as db_engine
from lumen.effects.geometry import led_positions, scene_bounds
from lumen.effects.graph import EvalContext, evaluate_graph
from lumen.effects.nodes import NODE_REGISTRY
from lumen.models.device import Device
from lumen.models.effect import Effect
from lumen.models.fixture import Fixture
from lumen.models.scene import Scene
from lumen.output import device_manager

logger = logging.getLogger(__name__)

_PREVIEW_EVERY_N_TICKS = 2
_AUDIO_BROADCAST_HZ = 10.0


class RenderLoop:
    def __init__(self) -> None:
        self._capture = AudioCapture()
        self._analyzer = AudioAnalyzer()
        self._latest_audio = AudioFrame(
            level=0.0,
            bands=np.zeros(NUM_BANDS, dtype=np.float32),
            low=0.0,
            mid=0.0,
            high=0.0,
            beat=0.0,
        )
        self._node_state: dict[int, dict[str, Any]] = {}
        self._start_time = time.monotonic()
        self._tick = 0
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def live_audio(self) -> AudioFrame:
        return self._latest_audio

    def elapsed_time(self) -> float:
        return time.monotonic() - self._start_time

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        try:
            self._capture.start()
        except Exception:
            logger.exception("failed to start audio capture, continuing without audio")

        drain_task = asyncio.create_task(self._drain_audio())
        period = 1.0 / max(settings.render_fps, 1)
        try:
            while self._running:
                tick_start = time.monotonic()
                await self._tick_once()
                elapsed = time.monotonic() - tick_start
                await asyncio.sleep(max(period - elapsed, 0.0))
        finally:
            drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await drain_task
            self._capture.stop()

    async def _drain_audio(self) -> None:
        while self._running:
            try:
                block = await asyncio.wait_for(self._capture.get(), timeout=0.5)
            except TimeoutError:
                continue
            except Exception:
                logger.exception("audio capture read failed")
                continue
            self._latest_audio = self._analyzer.analyze(block)

    async def _tick_once(self) -> None:
        self._tick += 1
        now = time.monotonic() - self._start_time
        console_state = console.snapshot()

        with Session(db_engine) as session:
            scene = session.exec(select(Scene).where(Scene.active)).first()
            if scene is None:
                return
            fixtures_by_id = {f.id: f for f in session.exec(select(Fixture)).all()}
            devices_by_id = {d.id: d for d in session.exec(select(Device)).all()}
            effects_by_id = {e.id: e for e in session.exec(select(Effect)).all()}

        bounds = scene_bounds([f.points for f in fixtures_by_id.values()])
        device_buffers: dict[int, np.ndarray] = {}
        preview: dict[str, list[list[int]]] = {}

        for assignment in scene.assignments:
            effect = effects_by_id.get(assignment.get("effect_id"))
            if effect is None:
                continue

            fixture_ids = assignment.get("fixture_ids")
            if fixture_ids == "all":
                target_fixtures = list(fixtures_by_id.values())
            else:
                target_fixtures = [
                    fixtures_by_id[fid] for fid in fixture_ids or [] if fid in fixtures_by_id
                ]

            brightness = float(assignment.get("brightness", 1.0)) * console_state.master_brightness
            param_overrides = self._resolve_param_overrides(effect, assignment, console_state)

            for fixture in target_fixtures:
                colors = self._render_fixture(
                    fixture, effect, param_overrides, now, console_state.hype, bounds
                )
                colors = np.clip(colors, 0.0, 1.0) * brightness
                colors = np.clip(colors, 0.0, 1.0)
                self._accumulate_device_buffer(device_buffers, devices_by_id, fixture, colors)
                preview[str(fixture.id)] = (colors * 255.0).astype(np.uint8).tolist()

        try:
            await device_manager.push_frame(device_buffers)
        except Exception:
            logger.exception("device output failed for this frame")

        if preview and self._tick % _PREVIEW_EVERY_N_TICKS == 0:
            await manager.broadcast({"type": "frame", "fixtures": preview})

        audio_every_n_ticks = max(int(settings.render_fps / _AUDIO_BROADCAST_HZ), 1)
        if self._tick % audio_every_n_ticks == 0:
            frame = self._latest_audio
            await manager.broadcast(
                {
                    "type": "audio",
                    "level": frame.level,
                    "bands": frame.bands.tolist(),
                    "beat": frame.beat,
                }
            )

    def _resolve_param_overrides(
        self, effect: Effect, assignment: dict[str, Any], console_state: ConsoleState
    ) -> dict[tuple[str, str], float]:
        overrides: dict[tuple[str, str], float] = {}
        scene_params = assignment.get("params") or {}
        for exposed in effect.exposed_params:
            node_id = exposed["node_id"]
            param_key = exposed["param_key"]
            override_key = f"{effect.id}:{param_key}"
            if override_key in console_state.param_overrides:
                value = console_state.param_overrides[override_key]
            elif param_key in scene_params:
                value = scene_params[param_key]
            else:
                continue
            overrides[(node_id, param_key)] = value
        return overrides

    def _render_fixture(
        self,
        fixture: Fixture,
        effect: Effect,
        param_overrides: dict[tuple[str, str], float],
        now: float,
        hype: float,
        bounds: tuple[np.ndarray, np.ndarray] | None,
    ) -> np.ndarray:
        positions = led_positions(fixture.points, fixture.led_count, reverse=fixture.reverse)
        node_state = self._node_state.setdefault(fixture.id, {})
        context = EvalContext(
            n=fixture.led_count,
            positions=positions,
            time=now,
            audio=self._latest_audio,
            hype=hype,
            state=node_state,
            scene_bounds=bounds,
        )
        try:
            colors, _node_outputs = evaluate_graph(
                effect.graph, NODE_REGISTRY, context, param_overrides
            )
            return colors
        except Exception:
            logger.exception("effect %r failed to evaluate for fixture %r", effect.id, fixture.id)
            return np.zeros((fixture.led_count, 3), dtype=np.float32)

    def _accumulate_device_buffer(
        self,
        device_buffers: dict[int, np.ndarray],
        devices_by_id: dict[int, Device],
        fixture: Fixture,
        colors: np.ndarray,
    ) -> None:
        device = devices_by_id.get(fixture.device_id)
        if device is None:
            return
        buffer = device_buffers.get(device.id)
        if buffer is None:
            buffer = np.zeros((max(device.led_count, 0), 3), dtype=np.uint8)
            device_buffers[device.id] = buffer
        start = fixture.start_channel
        end = min(start + fixture.led_count, buffer.shape[0])
        count = max(end - start, 0)
        if count:
            buffer[start:end] = (colors[:count] * 255.0).astype(np.uint8)


_render_loop = RenderLoop()


async def render_loop() -> None:
    await _render_loop.run()


def start_render_loop() -> asyncio.Task[None]:
    return _render_loop.start()


async def stop_render_loop() -> None:
    await _render_loop.stop()


def live_audio() -> AudioFrame:
    """Latest analyzed audio frame, for callers outside the render loop (the
    effect editor's debug preview) that want Audio/Beat nodes to animate
    against the same live signal the real show uses."""
    return _render_loop.live_audio()


def elapsed_time() -> float:
    return _render_loop.elapsed_time()
