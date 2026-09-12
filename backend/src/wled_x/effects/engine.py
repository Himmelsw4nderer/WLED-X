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
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from sqlmodel import Session, select

from wled_x import db
from wled_x.api.schemas import ConsoleState
from wled_x.api.ws import manager
from wled_x.audio.analysis import NUM_BANDS, AudioAnalyzer, AudioFrame
from wled_x.audio.capture import AudioCapture
from wled_x.config import settings
from wled_x.console.state import console
from wled_x.effects.color_schemes import resolve_scheme_colors
from wled_x.effects.geometry import led_positions, scene_bounds
from wled_x.effects.graph import EvalContext, evaluate_graph
from wled_x.effects.nodes import NODE_REGISTRY
from wled_x.effects.phrase_clock import PhraseClock
from wled_x.models.audio_source import AudioSourceConfig
from wled_x.models.device import Device
from wled_x.models.effect import Effect
from wled_x.models.fixture import Fixture
from wled_x.models.scene import Scene
from wled_x.output import device_manager

if TYPE_CHECKING:
    from wled_x.preview_window import LivePreviewWindow

logger = logging.getLogger(__name__)

# LED colors are computed every tick regardless (the render loop always runs
# at settings.render_fps for real device output) -- this only throttles how
# often the *browser preview* gets a WS "frame" message. 1 = broadcast every
# tick, matching render_fps, for the smoothest possible 3D view; raise this
# again if a scene with many fixtures/LEDs ever makes that WS traffic itself
# the bottleneck.
_PREVIEW_EVERY_N_TICKS = 1
_AUDIO_BROADCAST_HZ = 10.0

# Name of the always-on desktop/system-audio source. `EvalContext.audio` and
# `live_audio()` mirror this one specifically, so every existing node/caller
# that doesn't know about multi-source audio keeps working unchanged; a
# node with a Source param can instead look any name up in
# `EvalContext.audio_sources` / `live_audio_sources()`.
PRIMARY_SOURCE = "desktop"
MIC_SOURCE = "mic"


def _empty_frame() -> AudioFrame:
    return AudioFrame(
        level=0.0,
        bands=np.zeros(NUM_BANDS, dtype=np.float32),
        low=0.0,
        mid=0.0,
        high=0.0,
        beat=0.0,
    )


@dataclass
class _AudioSource:
    capture: AudioCapture
    analyzer: AudioAnalyzer
    frame: AudioFrame
    mode: str
    device: str | None


class RenderLoop:
    def __init__(self) -> None:
        # DB-free placeholder for the primary source, seeded from the env
        # defaults -- so live_audio()/live_audio_sources() are always safe to
        # call, even before run() has loaded the real config from
        # AudioSourceConfig (tests with render_enabled=False, or the instant
        # before the loop's first tick). reconfigure_audio_sources() (called
        # from run(), and again any time the device picker changes something)
        # replaces this with whatever's actually configured in the DB.
        self._sources: dict[str, _AudioSource] = {
            PRIMARY_SOURCE: self._build_source("loopback", settings.audio_device),
        }
        self._node_state: dict[int, dict[str, Any]] = {}
        self._start_time = time.monotonic()
        self._tick = 0
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._drain_tasks: dict[str, asyncio.Task[None]] = {}
        # Rolling cost of _tick_once() itself (excludes the inter-tick sleep),
        # so the optional local preview window can show real render capacity.
        self._tick_ms: deque[float] = deque(maxlen=120)
        self._preview_window: LivePreviewWindow | None = None
        # Show-level beat/phrase counter, fed from the console-selected audio
        # source each tick. Scene-playlist automation attaches to _playlist_runner
        # in run() when that module is present (added separately).
        self._phrase_clock = PhraseClock()
        self._playlist_runner: Any = None
        # Last active Scene.id we rendered; when it changes (console pick or a
        # playlist advance) we wipe the console's live fader overrides so the
        # incoming scene starts from its own stored params, not the last one's.
        self._active_scene_id: int | None = None

    def _build_source(self, mode: str, device: str | None) -> _AudioSource:
        return _AudioSource(
            capture=AudioCapture(device=device, mode=mode),
            analyzer=AudioAnalyzer(),
            frame=_empty_frame(),
            mode=mode,
            device=device,
        )

    def selected_source_name(self) -> str:
        """The audio source the console has picked to drive every audio node
        and the phrase-clock, falling back to the always-present primary."""
        name = console.snapshot().audio_source
        return name if name in self._sources else PRIMARY_SOURCE

    def live_audio(self) -> AudioFrame:
        source = self._sources.get(self.selected_source_name())
        if source is None:
            return _empty_frame()
        return source.analyzer.project(source.frame, time.monotonic())

    def phrase_clock_state(self) -> Any:
        return self._phrase_clock.state()

    def live_audio_sources(self) -> dict[str, AudioFrame]:
        now_wall = time.monotonic()
        return {
            name: source.analyzer.project(source.frame, now_wall)
            for name, source in self._sources.items()
        }

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
        await self.reconfigure_audio_sources()
        self._maybe_open_preview_window()
        self._maybe_attach_playlist_runner()

        period = 1.0 / max(settings.render_fps, 1)
        try:
            while self._running:
                tick_start = time.monotonic()
                await self._tick_once()
                elapsed = time.monotonic() - tick_start
                self._tick_ms.append(elapsed * 1000.0)
                await asyncio.sleep(max(period - elapsed, 0.0))
        finally:
            for name in list(self._drain_tasks):
                await self._stop_source(name)
            if self._preview_window is not None:
                self._preview_window.stop()
                self._preview_window = None

    def _maybe_open_preview_window(self) -> None:
        if not settings.preview_window or self._preview_window is not None:
            return
        try:
            from wled_x.preview_window import LivePreviewWindow

            self._preview_window = LivePreviewWindow()
            logger.info("local preview window enabled (WLEDX_PREVIEW_WINDOW)")
        except Exception:
            logger.warning("could not open the local preview window, continuing without it",
                           exc_info=True)

    def _maybe_attach_playlist_runner(self) -> None:
        """Scene-playlist automation is optional and lives in its own module;
        attach it if that module is present so a build without it still runs."""
        if self._playlist_runner is not None:
            return
        try:
            from wled_x.effects.playlist_runner import PlaylistRunner
        except ImportError:
            return
        self._playlist_runner = PlaylistRunner()

    async def reconfigure_audio_sources(self) -> None:
        """(Re)builds `self._sources` to match the `AudioSourceConfig` table,
        starting/stopping/replacing individual captures live as needed.
        Called from `run()` on startup and again by the device-picker API
        (`PUT /api/audio/sources/{name}`) any time the user changes a
        source's device -- no full render-loop restart required. Safe to
        call before `run()` too (e.g. from a test or another route): it just
        updates `self._sources` without starting anything, since `_running`
        is still False at that point."""
        with Session(db.engine) as session:
            rows = list(session.exec(select(AudioSourceConfig)).all())

        seen = set()
        for row in rows:
            seen.add(row.name)
            current = self._sources.get(row.name)
            changed = current is None or current.mode != row.mode or current.device != row.device
            if changed:
                if row.name in self._drain_tasks:
                    await self._stop_source(row.name)
                self._sources[row.name] = self._build_source(row.mode, row.device)

            is_running = row.name in self._drain_tasks
            if self._running and row.enabled and not is_running:
                await self._start_source(row.name)
            elif (not row.enabled or not self._running) and is_running:
                await self._stop_source(row.name)

        # A source removed from the DB entirely (not just disabled) stops
        # getting a frame -- but the primary source always stays, so every
        # node still has *something* to fall back to via context.audio.
        for name in list(self._sources):
            if name not in seen and name != PRIMARY_SOURCE:
                await self._stop_source(name)
                del self._sources[name]

    async def _start_source(self, name: str) -> None:
        source = self._sources[name]
        try:
            source.capture.start()
        except Exception:
            logger.exception(
                "failed to start audio capture for source %r, continuing without it", name
            )
        self._drain_tasks[name] = asyncio.create_task(self._drain_audio(name))

    async def _stop_source(self, name: str) -> None:
        task = self._drain_tasks.pop(name, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        source = self._sources.get(name)
        if source is not None:
            source.capture.stop()

    async def _drain_audio(self, name: str) -> None:
        while self._running:
            source = self._sources[name]
            try:
                block = await asyncio.wait_for(source.capture.get(), timeout=0.5)
            except TimeoutError:
                continue
            except Exception:
                logger.exception("audio capture read failed for source %r", name)
                continue
            source.frame = source.analyzer.analyze(block)

    async def _tick_once(self) -> None:
        self._tick += 1
        now_wall = time.monotonic()
        now = now_wall - self._start_time
        console_state = console.snapshot()

        # Beat fields (beat / bass_onset / beat_phase) recomputed on the render
        # clock so they move smoothly at render_fps instead of stepping at the
        # ~47 Hz audio-block rate -- see AudioAnalyzer.project().
        audio_frames = {
            name: source.analyzer.project(source.frame, now_wall)
            for name, source in self._sources.items()
        }
        selected = console_state.audio_source
        primary_frame = (
            audio_frames.get(selected)
            or audio_frames.get(PRIMARY_SOURCE)
            or _empty_frame()
        )

        # Advance the show-level phrase-clock and let any playlist automation
        # react (it may flip Scene.active), before we read the active scene.
        phrase_tick = self._phrase_clock.tick(primary_frame.beat_phase, primary_frame.bpm)
        if self._playlist_runner is not None:
            try:
                await self._playlist_runner.tick(
                    phrase_tick, self._phrase_clock, console_state, now_wall
                )
            except Exception:
                logger.exception("playlist runner tick failed")

        with Session(db.engine) as session:
            scene = session.exec(select(Scene).where(Scene.active)).first()
            if scene is None:
                self._active_scene_id = None
                self._broadcast_phrase_and_audio(primary_frame, audio_frames)
                return
            fixtures_by_id = {f.id: f for f in session.exec(select(Fixture)).all()}
            devices_by_id = {d.id: d for d in session.exec(select(Device)).all()}
            effects_by_id = {e.id: e for e in session.exec(select(Effect)).all()}
            color_scheme_colors = resolve_scheme_colors(
                session, console_state.active_color_scheme_id
            )

        if scene.id != self._active_scene_id:
            self._active_scene_id = scene.id
            # New scene live -> drop the outgoing scene's fader rides and render
            # this frame from the incoming scene's own stored params.
            await console.clear_param_overrides()
            console_state = console.snapshot()
            # Also wipe every node's working state -- Counters restart, Square's
            # phase resets, and (the point of this for a "just white" show) a
            # Scheme Random Color node redraws so switching scenes/effects
            # visibly picks a new color instead of holding whatever it drew
            # for the outgoing scene.
            self._node_state.clear()

        bounds = scene_bounds([f.points for f in fixtures_by_id.values()])
        device_buffers: dict[int, np.ndarray] = {}
        preview: dict[str, list[list[int]]] = {}
        preview_names: dict[str, str] = {}

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
                    fixture, effect, param_overrides, now, console_state.hype, bounds,
                    primary_frame, audio_frames, color_scheme_colors,
                )
                colors = np.clip(colors, 0.0, 1.0) * brightness
                colors = np.clip(colors, 0.0, 1.0)
                self._accumulate_device_buffer(device_buffers, devices_by_id, fixture, colors)
                preview[str(fixture.id)] = (colors * 255.0).astype(np.uint8).tolist()
                preview_names[str(fixture.id)] = fixture.name

        try:
            await device_manager.push_frame(device_buffers)
        except Exception:
            logger.exception("device output failed for this frame")

        if preview and self._tick % _PREVIEW_EVERY_N_TICKS == 0:
            manager.broadcast_latest({"type": "frame", "fixtures": preview})

        if self._preview_window is not None and preview:
            stats = self._render_stats_line(preview, primary_frame)
            self._preview_window.submit(preview, preview_names, stats)

        self._broadcast_phrase_and_audio(primary_frame, audio_frames)

    def _broadcast_phrase_and_audio(
        self, primary_frame: AudioFrame, audio_frames: dict[str, AudioFrame]
    ) -> None:
        every_n = max(int(settings.render_fps / _AUDIO_BROADCAST_HZ), 1)
        if self._tick % every_n != 0:
            return

        message: dict[str, Any] = {
            "type": "audio",
            "level": primary_frame.level,
            "bands": primary_frame.bands.tolist(),
            "beat": primary_frame.beat,
            "bpm": primary_frame.bpm,
        }
        if MIC_SOURCE in audio_frames:
            mic_frame = audio_frames[MIC_SOURCE]
            message["mic"] = {"level": mic_frame.level, "beat": mic_frame.beat}
        manager.broadcast_latest(message)
        manager.broadcast_latest({"type": "phrase", **self._phrase_clock.state().model_dump()})

    def _render_stats_line(
        self, preview: dict[str, list[list[int]]], audio: AudioFrame
    ) -> str:
        total_leds = sum(len(v) for v in preview.values())
        samples = list(self._tick_ms)
        audio_line = (
            f"audio: level {audio.level:4.2f}  beat {audio.beat:4.2f}  "
            f"phase {audio.beat_phase:4.2f}  bpm {audio.bpm:5.1f}"
        )
        if not samples:
            return f"{len(preview)} fixtures / {total_leds} LEDs\n{audio_line}"
        mean = sum(samples) / len(samples)
        worst = max(samples)
        capacity = 1000.0 / mean if mean > 0 else 0.0
        headroom = capacity / max(settings.render_fps, 1)
        return (
            f"tick mean {mean:5.2f} ms   max {worst:5.2f} ms   |   "
            f"capacity ~{capacity:6.0f} fps  (x{headroom:.1f} over {settings.render_fps})   |   "
            f"{len(preview)} fixtures / {total_leds} LEDs\n{audio_line}"
        )

    def _resolve_param_overrides(
        self, effect: Effect, assignment: dict[str, Any], console_state: ConsoleState
    ) -> dict[tuple[str, str], float | str]:
        overrides: dict[tuple[str, str], float | str] = {}
        scene_params = assignment.get("params") or {}
        for exposed in effect.exposed_params:
            node_id = exposed["node_id"]
            param_key = exposed["param_key"]
            # Must include node_id, not just param_key: two instances of the same
            # node type (e.g. two Constant nodes) can both expose a param called
            # "value", and without node_id in the key they'd collide onto the same
            # console override, making them impossible to control separately.
            override_key = f"{effect.id}:{node_id}:{param_key}"
            scene_key = f"{node_id}:{param_key}"
            if override_key in console_state.param_overrides:
                # Live fader ride, this frame.
                value = console_state.param_overrides[override_key]
            elif scene_key in scene_params:
                # Persisted fader-bank value for this scene.
                value = scene_params[scene_key]
            elif param_key in scene_params:
                # Legacy scenes keyed params by bare param_key.
                value = scene_params[param_key]
            else:
                continue
            overrides[(node_id, param_key)] = value
        return overrides

    def _render_fixture(
        self,
        fixture: Fixture,
        effect: Effect,
        param_overrides: dict[tuple[str, str], float | str],
        now: float,
        hype: float,
        bounds: tuple[np.ndarray, np.ndarray] | None,
        primary: AudioFrame,
        audio_frames: dict[str, AudioFrame],
        color_scheme: np.ndarray,
    ) -> np.ndarray:
        positions = led_positions(fixture.points, fixture.led_count, reverse=fixture.reverse)
        node_state = self._node_state.setdefault(fixture.id, {})
        context = EvalContext(
            n=fixture.led_count,
            positions=positions,
            time=now,
            audio=primary,
            hype=hype,
            state=node_state,
            scene_bounds=bounds,
            audio_sources=audio_frames,
            color_scheme=color_scheme,
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
    """Latest analyzed audio frame from the console-selected source, for
    callers outside the render loop (the effect editor's debug preview) that
    want audio nodes to animate against the same live signal the real show
    uses."""
    return _render_loop.live_audio()


def phrase_clock_state() -> Any:
    """Live PhraseClockState snapshot, for GET /api/phrase and the console."""
    return _render_loop.phrase_clock_state()


def playlist_runner() -> Any:
    """The render loop's PlaylistRunner, or None when the loop hasn't attached
    one (tests with render disabled) -- callers then fall back to inline DB
    math. See wled_x.effects.playlist_runner."""
    return _render_loop._playlist_runner


def render_loop_instance() -> "RenderLoop":
    """The process-wide render loop, for automation (e.g. the playlist runner)
    that needs to read the phrase-clock or nudge it."""
    return _render_loop


def live_audio_sources() -> dict[str, AudioFrame]:
    """Latest analyzed frame from every running audio source, keyed by name
    (e.g. "desktop", "mic"), for the same debug-preview use case as
    `live_audio()` but covering nodes with a Source param."""
    return _render_loop.live_audio_sources()


async def reconfigure_audio_sources() -> None:
    """Re-reads `AudioSourceConfig` from the DB and swaps any changed
    capture live, without restarting the render loop. Called by the audio
    device picker's API (`PUT /api/audio/sources/{name}`) after it writes a
    new device/mode/enabled selection."""
    await _render_loop.reconfigure_audio_sources()


def elapsed_time() -> float:
    return _render_loop.elapsed_time()
