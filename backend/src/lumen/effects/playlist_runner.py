"""Scene-playlist automation.

One `PlaylistRunner` lives on the render loop (attached in
`RenderLoop._maybe_attach_playlist_runner`). Each tick it reads the single
`active` `Playlist` from the DB, decides -- per the playlist's
`advance_trigger` -- whether it's time to move on, and if so flips
`Scene.active` to the next entry's scene (same "exactly one active" convention
as `routes_scenes`). It also answers manual prev/next from the API via
`advance()`, and exposes a `status()` snapshot for the console panel.

All mutable position state lives on the instance so `tick()` is cheap to call
~60x/s; the only per-tick DB work is one indexed `SELECT ... WHERE active`.
"""

import logging
import random
import time
from typing import Any

from sqlmodel import Session, select

from lumen import db
from lumen.api.schemas import PlaylistStatus
from lumen.api.ws import manager
from lumen.models.playlist import Playlist
from lumen.models.scene import Scene

logger = logging.getLogger(__name__)


def compute_next_index(
    mode: str, index: int, count: int, delta: int, *, pingpong_dir: int = 1
) -> tuple[int, int]:
    """Pure index math for one advance step. Returns
    ``(next_index, new_pingpong_dir)``.

    - ``sequential``: wrap ``index + delta``.
    - ``shuffle``: a random index != ``index`` (no immediate repeat).
    - ``pingpong``: bounce between ``0`` and ``count - 1``; ``delta``'s sign
      picks travel direction relative to the current ``pingpong_dir``.
    """
    if count <= 1:
        return 0, pingpong_dir
    if mode == "shuffle":
        return random.choice([i for i in range(count) if i != index]), pingpong_dir
    if mode == "pingpong":
        step = pingpong_dir if delta >= 0 else -pingpong_dir
        nxt = index + step
        if nxt >= count:
            return count - 2, -1
        if nxt < 0:
            return 1, 1
        return nxt, pingpong_dir
    return (index + delta) % count, pingpong_dir


def activate_scene(session: Session, scene_id: int) -> bool:
    """Make ``scene_id`` the sole active scene. Returns False (no-op) if that
    scene no longer exists."""
    target = session.get(Scene, scene_id)
    if target is None:
        return False
    for other in session.exec(select(Scene).where(Scene.id != scene_id)).all():
        if other.active:
            other.active = False
            session.add(other)
    if not target.active:
        target.active = True
        session.add(target)
    session.commit()
    return True


def step_playlist(
    session: Session,
    scene_ids: list[int],
    mode: str,
    index: int,
    delta: int,
    *,
    pingpong_dir: int = 1,
) -> tuple[int, int | None, int]:
    """Advance one entry from ``index`` and activate the resulting scene,
    skipping past entries whose scene has been deleted. Returns
    ``(new_index, activated_scene_id | None, new_pingpong_dir)``."""
    count = len(scene_ids)
    if count == 0:
        return index, None, pingpong_dir
    nxt, new_dir = compute_next_index(mode, index, count, delta, pingpong_dir=pingpong_dir)
    walk = 1 if delta >= 0 else -1
    for _ in range(count):
        if activate_scene(session, scene_ids[nxt]):
            return nxt, scene_ids[nxt], new_dir
        nxt = (nxt + walk) % count
    return nxt, None, new_dir


def _entry_scene_ids(playlist: Playlist) -> list[int]:
    return [int(e["scene_id"]) for e in (playlist.entries or []) if "scene_id" in e]


class PlaylistRunner:
    def __init__(self) -> None:
        self._playlist_id: int | None = None
        self._entries_key: tuple[int, ...] = ()
        self._mode: str = ""
        self._index: int = 0
        self._pingpong_dir: int = 1
        self._beats_seen: int = 0
        self._bars_seen: int = 0
        self._last_advance_wall: float = 0.0
        self._prev_hype: float = 0.0

    # -- internal ---------------------------------------------------------

    def _reset(self) -> None:
        self.__init__()

    def _sync_to(self, playlist: Playlist, scene_ids: list[int], now: float) -> bool:
        """If the active playlist (or its entries/mode) changed since the last
        call, snap internal position back to entry 0. Returns True when it did."""
        key = tuple(scene_ids)
        if (
            playlist.id == self._playlist_id
            and key == self._entries_key
            and playlist.mode == self._mode
        ):
            return False
        self._playlist_id = playlist.id
        self._entries_key = key
        self._mode = playlist.mode
        self._index = 0
        self._pingpong_dir = 1
        self._beats_seen = 0
        self._bars_seen = 0
        self._last_advance_wall = now
        return True

    def _peek_next_scene_id(self, scene_ids: list[int]) -> int | None:
        count = len(scene_ids)
        if count == 0:
            return None
        if self._mode == "shuffle":
            return None  # unknowable until we actually roll
        nxt, _ = compute_next_index(
            self._mode, self._index, count, 1, pingpong_dir=self._pingpong_dir
        )
        return scene_ids[nxt]

    def _broadcast(self) -> None:
        try:
            manager.broadcast_latest({"type": "playlist", **self.status().model_dump()})
        except RuntimeError:
            # No running event loop (called from a sync API worker thread with
            # no WS clients). Nothing to broadcast to in that case anyway.
            pass

    # -- render-loop entry point ---------------------------------------------

    async def tick(self, phrase_tick: Any, clock: Any, console_state: Any, now: float) -> None:
        with Session(db.engine) as session:
            playlist = session.exec(select(Playlist).where(Playlist.active)).first()
            if playlist is None:
                if self._playlist_id is not None:
                    self._reset()
                return

            scene_ids = _entry_scene_ids(playlist)

            if self._sync_to(playlist, scene_ids, now):
                self._prev_hype = float(getattr(console_state, "hype", 0.0))
                if scene_ids:
                    activate_scene(session, scene_ids[0])
                self._broadcast()
                return

            if not scene_ids:
                return

            if self._should_advance(phrase_tick, playlist, console_state, now):
                self._index, _sid, self._pingpong_dir = step_playlist(
                    session,
                    scene_ids,
                    self._mode,
                    self._index,
                    1,
                    pingpong_dir=self._pingpong_dir,
                )
                self._beats_seen = 0
                self._bars_seen = 0
                self._last_advance_wall = now
                self._broadcast()

    def _should_advance(
        self, phrase_tick: Any, playlist: Playlist, console_state: Any, now: float
    ) -> bool:
        trigger = playlist.advance_trigger
        if trigger == "beats":
            if getattr(phrase_tick, "beat_advanced", False):
                self._beats_seen += 1
            return self._beats_seen >= max(playlist.advance_beats, 1)
        if trigger == "bars":
            if getattr(phrase_tick, "bar_advanced", False):
                self._bars_seen += 1
            return self._bars_seen >= max(playlist.advance_beats, 1)
        if trigger == "tempo_change":
            return bool(getattr(phrase_tick, "tempo_changed", False))
        if trigger == "time":
            return now - self._last_advance_wall >= playlist.advance_seconds
        if trigger == "hype":
            hype = float(getattr(console_state, "hype", 0.0))
            rising = self._prev_hype < playlist.hype_threshold <= hype
            self._prev_hype = hype
            return rising
        return False  # "manual"

    # -- API entry points --------------------------------------------------

    def advance(self, delta: int) -> PlaylistStatus:
        """Manual next(+1) / prev(-1) from the route. Applies immediately using
        the same index math + scene activation, ignoring the advance trigger."""
        with Session(db.engine) as session:
            playlist = session.exec(select(Playlist).where(Playlist.active)).first()
            if playlist is None:
                self._reset()
                return PlaylistStatus()
            scene_ids = _entry_scene_ids(playlist)
            self._sync_to(playlist, scene_ids, time.monotonic())
            if scene_ids:
                self._index, _sid, self._pingpong_dir = step_playlist(
                    session,
                    scene_ids,
                    self._mode,
                    self._index,
                    delta,
                    pingpong_dir=self._pingpong_dir,
                )
                self._beats_seen = 0
                self._bars_seen = 0
                self._last_advance_wall = time.monotonic()
        self._broadcast()
        return self.status()

    def status(self) -> PlaylistStatus:
        with Session(db.engine) as session:
            playlist = session.exec(select(Playlist).where(Playlist.active)).first()
            if playlist is None:
                return PlaylistStatus()
            scene_ids = _entry_scene_ids(playlist)
            count = len(scene_ids)
            index = self._index % count if count else 0
            status = PlaylistStatus(
                playlist_id=playlist.id,
                index=index,
                scene_id=scene_ids[index] if count else None,
                next_scene_id=self._peek_next_scene_id(scene_ids),
            )
            trigger = playlist.advance_trigger
            if trigger == "beats":
                status.beats_until_advance = max(playlist.advance_beats - self._beats_seen, 0)
            elif trigger == "bars":
                status.beats_until_advance = max(playlist.advance_beats - self._bars_seen, 0)
            elif trigger == "time":
                left = playlist.advance_seconds - (time.monotonic() - self._last_advance_wall)
                status.seconds_until_advance = round(max(left, 0.0), 1)
            return status
