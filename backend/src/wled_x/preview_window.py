"""Realtime LED preview + render-speed check, with no webserver in the path.

Two ways in:

* **`LivePreviewWindow`** -- an in-process Tk window the running backend can
  open (set `WLEDX_PREVIEW_WINDOW=true`). It's fed straight from the render
  loop, so it shows the *real* active scene reacting to *real* audio, the
  exact colours being sent to the fixtures, plus live render timing -- with
  no browser or WebSocket involved.

* **the `python -m wled_x.preview_window` CLI** -- a standalone benchmark that
  loads the active scene from the DB and evaluates every fixture's graph in a
  tight loop, printing the bare cost of `evaluate_graph` per frame. Audio
  here is a synthetic 128 BPM beat (it never opens a capture device):

      python -m wled_x.preview_window                # active scene, Tk window
      python -m wled_x.preview_window --fullspeed    # ignore the FPS cap, measure max throughput
      python -m wled_x.preview_window --headless     # no window, just print stats (for SSH / CI)
      python -m wled_x.preview_window --effect 3     # force one effect onto every fixture

Keys in the CLI window: [space] pause, [r] reload scene/effects from the DB, [q] quit.
"""

from __future__ import annotations

import argparse
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlmodel import Session, create_engine, select

from wled_x import db
from wled_x.audio.analysis import NUM_BANDS, AudioFrame
from wled_x.config import settings
from wled_x.db import init_db
from wled_x.effects.geometry import led_positions, scene_bounds
from wled_x.effects.graph import EvalContext, GraphError, evaluate_graph
from wled_x.effects.nodes import NODE_REGISTRY
from wled_x.models.effect import Effect
from wled_x.models.fixture import Fixture
from wled_x.models.scene import Scene

logger = logging.getLogger(__name__)


def _anchor_db_to_backend_root() -> Path:
    """`settings.db_path` is relative ("wled_x.db"), so `wled_x.db.engine` points
    at whatever the *current directory* is when the process starts -- the
    server always runs from `backend/`, but this tool gets run from all over.
    Re-point the engine at `backend/wled_x.db` (this file is
    backend/src/wled_x/preview_window.py) so we always read the same DB the
    server writes, no matter the cwd. An absolute WLEDX_DB_PATH is left alone.
    """
    configured = Path(settings.db_path)
    if configured.is_absolute():
        return configured
    resolved = Path(__file__).resolve().parents[2] / configured
    db.engine = create_engine(
        f"sqlite:///{resolved}", connect_args={"check_same_thread": False}
    )
    return resolved


@dataclass
class RenderTarget:
    """One fixture, plus everything precomputed for it that doesn't change
    frame to frame."""

    fixture_id: int
    name: str
    led_count: int
    positions: np.ndarray
    graph: dict
    overrides: dict[tuple[str, str], float]
    brightness: float
    state: dict


def _synthetic_audio(t: float) -> AudioFrame:
    """A plausible fake audio frame so audio-reactive nodes still animate
    (and still cost what they cost) without opening a capture device."""
    bpm = 128.0
    beat_hz = bpm / 60.0
    phase = (t * beat_hz) % 1.0
    beat = math.exp(-phase * 6.0)
    level = 0.35 + 0.3 * math.sin(t * 2.3) + 0.2 * beat
    bands = np.abs(np.sin(np.linspace(0.0, 3.0, NUM_BANDS) + t * 4.0)).astype(np.float32)
    bands *= 0.4 + 0.6 * beat
    return AudioFrame(
        level=float(np.clip(level, 0.0, 1.0)),
        bands=bands,
        low=float(0.5 * beat + 0.2),
        mid=float(0.3 + 0.2 * math.sin(t * 5.0)),
        high=float(0.2 + 0.2 * abs(math.sin(t * 9.0))),
        beat=float(beat),
        bass_onset=float(beat if phase < 0.1 else 0.0),
        bpm=bpm,
        beat_phase=float(phase),
    )


def _put_string(colors_u8: np.ndarray, scale: int, strip_h: int) -> str:
    """Build the `PhotoImage.put` argument for one LED strip: a block of
    `strip_h` identical rows, each LED widened to `scale` pixels."""
    cells = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors_u8]
    if scale > 1:
        cells = [c for c in cells for _ in range(scale)]
    row = "{" + " ".join(cells) + "}"
    return " ".join([row] * strip_h)


Bounds = tuple[np.ndarray, np.ndarray]


def _load_targets(
    session: Session, force_effect_id: int | None
) -> tuple[str, list[RenderTarget], Bounds | None]:
    scene = session.exec(select(Scene).where(Scene.active)).first()
    fixtures = {f.id: f for f in session.exec(select(Fixture)).all()}
    effects = {e.id: e for e in session.exec(select(Effect)).all()}
    if not fixtures:
        raise SystemExit("no fixtures in the DB -- add some in the app first")

    bounds = scene_bounds([f.points for f in fixtures.values()])

    assignments: list[dict]
    if force_effect_id is not None:
        if force_effect_id not in effects:
            raise SystemExit(f"no effect with id {force_effect_id}")
        assignments = [{"fixture_ids": "all", "effect_id": force_effect_id, "brightness": 1.0}]
        label = f"effect {force_effect_id} ({effects[force_effect_id].name}) on all fixtures"
    elif scene is not None:
        assignments = scene.assignments
        label = f"scene {scene.id!r} ({scene.name})"
    else:
        raise SystemExit("no active scene and no --effect given")

    targets: list[RenderTarget] = []
    for assignment in assignments:
        effect = effects.get(assignment.get("effect_id"))
        if effect is None:
            continue
        fixture_ids = assignment.get("fixture_ids")
        chosen = (
            list(fixtures.values())
            if fixture_ids == "all"
            else [fixtures[fid] for fid in fixture_ids or [] if fid in fixtures]
        )
        brightness = float(assignment.get("brightness", 1.0))
        scene_params = assignment.get("params") or {}
        overrides: dict[tuple[str, str], float] = {}
        for exposed in effect.exposed_params:
            key = exposed["param_key"]
            if key in scene_params:
                overrides[(exposed["node_id"], key)] = scene_params[key]

        for fixture in chosen:
            targets.append(
                RenderTarget(
                    fixture_id=fixture.id,
                    name=fixture.name,
                    led_count=fixture.led_count,
                    positions=led_positions(
                        fixture.points, fixture.led_count, reverse=fixture.reverse
                    ),
                    graph=effect.graph,
                    overrides=overrides,
                    brightness=brightness,
                    state={},
                )
            )
    if not targets:
        raise SystemExit("nothing to render (scene has no usable assignments)")

    # Group runs of the same fixture appearing twice cleanly: last assignment wins,
    # matching the engine's accumulate-then-overwrite-per-fixture behaviour closely
    # enough for a visual/perf check.
    deduped: dict[int, RenderTarget] = {}
    for target in targets:
        deduped[target.fixture_id] = target
    return label, list(deduped.values()), bounds


class Benchmark:
    def __init__(self, targets: list[RenderTarget], bounds: Bounds | None) -> None:
        self.targets = targets
        self.bounds = bounds
        self.frame_ms: deque[float] = deque(maxlen=240)
        self.eval_ms: deque[float] = deque(maxlen=240)
        self.tick_times: deque[float] = deque(maxlen=240)
        self.frames = 0
        self.start = time.perf_counter()

    def tick(self, now: float) -> list[tuple[RenderTarget, np.ndarray]]:
        audio = _synthetic_audio(now)
        results: list[tuple[RenderTarget, np.ndarray]] = []
        frame_start = time.perf_counter()
        eval_total = 0.0
        for target in self.targets:
            ctx = EvalContext(
                n=target.led_count,
                positions=target.positions,
                time=now,
                audio=audio,
                hype=0.0,
                state=target.state,
                scene_bounds=self.bounds,
                audio_sources={"desktop": audio, "mic": audio},
            )
            t0 = time.perf_counter()
            try:
                colors, _ = evaluate_graph(target.graph, NODE_REGISTRY, ctx, target.overrides)
            except GraphError as exc:
                raise SystemExit(f"graph error on {target.name!r}: {exc}") from exc
            eval_total += time.perf_counter() - t0
            colors = np.clip(colors, 0.0, 1.0) * target.brightness
            results.append((target, np.clip(colors, 0.0, 1.0)))
        self.frame_ms.append((time.perf_counter() - frame_start) * 1000.0)
        self.eval_ms.append(eval_total * 1000.0)
        self.tick_times.append(time.perf_counter())
        self.frames += 1
        return results

    def reset_stats(self) -> None:
        self.frame_ms.clear()
        self.eval_ms.clear()
        self.tick_times.clear()
        self.frames = 0
        self.start = time.perf_counter()

    def stats_line(self) -> str:
        if len(self.tick_times) < 2:
            return "warming up..."
        total_leds = sum(t.led_count for t in self.targets)
        span = self.tick_times[-1] - self.tick_times[0]
        fps = (len(self.tick_times) - 1) / span if span > 0 else 0.0
        ev = np.array(self.eval_ms)
        fr = np.array(self.frame_ms)
        return (
            f"{fps:6.1f} fps   |   eval/frame  mean {ev.mean():5.2f} ms  "
            f"p95 {np.percentile(ev, 95):5.2f}  max {ev.max():5.2f}   |   "
            f"full frame mean {fr.mean():5.2f} ms   |   "
            f"{len(self.targets)} fixtures / {total_leds} LEDs   |   "
            f"headroom x{(1000.0 / max(fr.mean(), 1e-6)) / max(settings.render_fps, 1):.1f} "
            f"vs {settings.render_fps} fps"
        )

def run_headless(bench: Benchmark, target_fps: float, duration: float) -> None:
    period = 0.0 if target_fps <= 0 else 1.0 / target_fps
    print(f"benchmarking for {duration:.0f}s ...")
    end = time.perf_counter() + duration
    last_print = 0.0
    while time.perf_counter() < end:
        tick_start = time.perf_counter()
        bench.tick(time.perf_counter() - bench.start)
        if time.perf_counter() - last_print > 1.0:
            print("  " + bench.stats_line().ljust(120), end="\r", flush=True)
            last_print = time.perf_counter()
        if period:
            time.sleep(max(period - (time.perf_counter() - tick_start), 0.0))
    print("\n\nfinal: " + bench.stats_line())


def run_window(bench: Benchmark, target_fps: float, reload_cb) -> None:
    import tkinter as tk

    strip_h = 22
    pad = 6
    max_leds = max(t.led_count for t in bench.targets)
    scale = max(1, min(12, 900 // max_leds))
    width = max_leds * scale

    root = tk.Tk()
    root.title("wled_x render-speed preview (no webserver)")
    root.configure(bg="#111")

    state = {"paused": False, "period": 0.0 if target_fps <= 0 else 1.0 / target_fps}

    images: dict[int, tk.PhotoImage] = {}
    for target in bench.targets:
        row = tk.Frame(root, bg="#111")
        row.pack(fill="x", padx=pad, pady=(pad, 0))
        tk.Label(
            row, text=f"{target.name} ({target.led_count})", width=16, anchor="w",
            fg="#ccc", bg="#111", font=("TkFixedFont", 9),
        ).pack(side="left")
        img = tk.PhotoImage(width=width, height=strip_h)
        images[target.fixture_id] = img
        tk.Label(row, image=img, bg="#111", bd=0).pack(side="left")

    stats = tk.Label(
        root, text="warming up...", fg="#0f0", bg="#111", anchor="w",
        font=("TkFixedFont", 10), justify="left",
    )
    stats.pack(fill="x", padx=pad, pady=pad)

    def draw(target: RenderTarget, colors: np.ndarray) -> None:
        u8 = (colors * 255.0).astype(np.uint8)
        images[target.fixture_id].put(_put_string(u8, scale, strip_h))

    def frame() -> None:
        if not state["paused"]:
            results = bench.tick(time.perf_counter() - bench.start)
            for target, colors in results:
                draw(target, colors)
            stats.configure(text=bench.stats_line())
        delay = max(int(state["period"] * 1000), 1) if state["period"] else 1
        root.after(delay, frame)

    def on_key(event: tk.Event) -> None:
        if event.keysym in ("q", "Escape"):
            root.destroy()
        elif event.keysym == "space":
            state["paused"] = not state["paused"]
        elif event.keysym == "r":
            bench.targets, bench.bounds = reload_cb()
            bench.reset_stats()
            stats.configure(text="reloaded from DB")

    root.bind("<Key>", on_key)
    root.after(1, frame)
    root.mainloop()


class LivePreviewWindow:
    """An in-process Tk window driven by the live render loop.

    The render-loop task only ever calls `submit()`, which drops the latest
    frame into a plain slot (assignment is atomic under the GIL) -- it never
    touches Tk and never blocks. Every Tk call happens on this object's own
    daemon thread, which repaints from that slot at
    `settings.preview_window_fps`.

    Construction is best-effort: if there's no display or tkinter is missing
    it logs a warning and every method becomes a no-op, so the backend is
    never taken down by the preview window.
    """

    def __init__(self) -> None:
        self._latest: tuple[dict[str, list], dict[str, str], str] | None = None
        self._stopping = False
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="wled_x-preview-window", daemon=True
        )
        self._thread.start()
        # Give the thread a moment to fail loudly (no DISPLAY, no tkinter)
        # rather than silently never drawing.
        self._ready.wait(timeout=5.0)

    def submit(self, frame: dict[str, list], names: dict[str, str], stats: str) -> None:
        self._latest = (frame, names, stats)

    def stop(self) -> None:
        self._stopping = True
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception:
            logger.warning("preview window disabled: tkinter not importable", exc_info=True)
            self._ready.set()
            return
        try:
            root = tk.Tk()
        except Exception:
            logger.warning(
                "preview window disabled: no display available (headless?)", exc_info=True
            )
            self._ready.set()
            return

        root.title("wled_x live preview -- render loop, no webserver")
        root.configure(bg="#111")
        root.protocol("WM_DELETE_WINDOW", lambda: setattr(self, "_stopping", True))

        strip_h = 20
        pad = 6
        interval_ms = max(int(1000 / max(settings.preview_window_fps, 1)), 10)
        rows: dict = {}
        ui: dict = {"scale": 1, "holders": [], "layout_key": ()}

        stats_label = tk.Label(
            root, text="waiting for first frame...", fg="#0f0", bg="#111",
            anchor="w", justify="left", font=("TkFixedFont", 10),
        )
        stats_label.pack(fill="x", padx=pad, pady=pad)

        def rebuild(frame: dict, names: dict) -> None:
            for holder in ui["holders"]:
                holder.destroy()
            ui["holders"] = []
            rows.clear()
            max_leds = max((len(v) for v in frame.values()), default=1)
            ui["scale"] = max(1, min(12, 900 // max(max_leds, 1)))
            for key, cells in frame.items():
                holder = tk.Frame(root, bg="#111")
                holder.pack(fill="x", padx=pad, pady=(pad, 0), before=stats_label)
                tk.Label(
                    holder, text=f"{names.get(key, key)} ({len(cells)})", width=16,
                    anchor="w", fg="#ccc", bg="#111", font=("TkFixedFont", 9),
                ).pack(side="left")
                img = tk.PhotoImage(width=max_leds * ui["scale"], height=strip_h)
                rows[key] = img
                tk.Label(holder, image=img, bg="#111", bd=0).pack(side="left")
                ui["holders"].append(holder)
            ui["layout_key"] = tuple(frame.keys())

        def redraw() -> None:
            if self._stopping:
                root.destroy()
                return
            latest = self._latest
            if latest is not None:
                frame, names, stats = latest
                if tuple(frame.keys()) != ui["layout_key"]:
                    rebuild(frame, names)
                for key, img in rows.items():
                    cells = frame.get(key)
                    if cells is not None:
                        u8 = np.asarray(cells, dtype=np.uint8)
                        img.put(_put_string(u8, ui["scale"], strip_h))
                stats_label.configure(text=stats)
            root.after(interval_ms, redraw)

        self._ready.set()
        root.after(interval_ms, redraw)
        try:
            root.mainloop()
        except Exception:
            logger.warning("preview window: Tk mainloop crashed", exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=float, default=settings.render_fps,
                        help=f"target frame rate (default render_fps = {settings.render_fps})")
    parser.add_argument("--fullspeed", action="store_true",
                        help="ignore --fps, render flat out (measures max throughput)")
    parser.add_argument("--headless", action="store_true",
                        help="no Tk window; run the benchmark and print stats")
    parser.add_argument("--duration", type=float, default=15.0,
                        help="headless run length in seconds (default: 15)")
    parser.add_argument("--effect", type=int, default=None,
                        help="force this effect id onto every fixture instead of the active scene")
    args = parser.parse_args()

    db_file = _anchor_db_to_backend_root()
    if not Path(db_file).exists():
        raise SystemExit(
            f"no DB at {db_file} -- start the app once so it gets created, "
            "or set WLEDX_DB_PATH to an absolute path"
        )
    print(f"db: {db_file}")
    init_db()
    force = args.effect

    def load() -> tuple[list[RenderTarget], Bounds | None]:
        with Session(db.engine) as session:
            label, targets, bounds = _load_targets(session, force)
        print(f"rendering: {label}  ({len(targets)} fixtures)")
        return targets, bounds

    bench = Benchmark(*load())
    target_fps = 0.0 if args.fullspeed else args.fps

    if args.headless:
        run_headless(bench, target_fps, args.duration)
    else:
        try:
            run_window(bench, target_fps, load)
        except Exception as exc:  # noqa: BLE001 -- headless box, no display, etc.
            print(f"couldn't open a window ({exc}); falling back to --headless")
            run_headless(bench, target_fps, args.duration)


if __name__ == "__main__":
    main()
