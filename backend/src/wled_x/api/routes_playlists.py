from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from wled_x.api.schemas import (
    PhraseClockState,
    PlaylistCreate,
    PlaylistRead,
    PlaylistStatus,
    PlaylistUpdate,
)
from wled_x.db import get_session
from wled_x.effects import engine
from wled_x.effects.playlist_runner import compute_next_index, step_playlist
from wled_x.models.playlist import ADVANCE_TRIGGERS, PLAYLIST_MODES, Playlist
from wled_x.models.scene import Scene

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

# The phrase-clock readout is its own one-route router so it can sit at /api
# rather than under /api/playlists; both get registered in main.py.
phrase_router = APIRouter(prefix="/api", tags=["playlists"])


def _validate(mode: str | None, trigger: str | None) -> None:
    if mode is not None and mode not in PLAYLIST_MODES:
        raise HTTPException(422, f"mode must be one of {list(PLAYLIST_MODES)}")
    if trigger is not None and trigger not in ADVANCE_TRIGGERS:
        raise HTTPException(422, f"advance_trigger must be one of {list(ADVANCE_TRIGGERS)}")


@router.get("", response_model=list[PlaylistRead])
def list_playlists(session: Session = Depends(get_session)) -> list[Playlist]:
    return list(session.exec(select(Playlist)).all())


@router.post("", response_model=PlaylistRead, status_code=201)
def create_playlist(
    payload: PlaylistCreate, session: Session = Depends(get_session)
) -> Playlist:
    _validate(payload.mode, payload.advance_trigger)
    playlist = Playlist(
        name=payload.name,
        entries=[e.model_dump() for e in payload.entries],
        mode=payload.mode,
        advance_trigger=payload.advance_trigger,
        advance_beats=payload.advance_beats,
        advance_seconds=payload.advance_seconds,
        hype_threshold=payload.hype_threshold,
    )
    session.add(playlist)
    session.commit()
    session.refresh(playlist)
    return playlist


@router.get("/status", response_model=PlaylistStatus)
def playlist_status() -> PlaylistStatus:
    runner = engine.playlist_runner()
    return runner.status() if runner is not None else PlaylistStatus()


@router.post("/deactivate", status_code=204)
def deactivate_playlists(session: Session = Depends(get_session)) -> None:
    for playlist in session.exec(select(Playlist).where(Playlist.active)).all():
        playlist.active = False
        session.add(playlist)
    session.commit()


@router.get("/{playlist_id}", response_model=PlaylistRead)
def get_playlist(playlist_id: int, session: Session = Depends(get_session)) -> Playlist:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "playlist not found")
    return playlist


@router.patch("/{playlist_id}", response_model=PlaylistRead)
def update_playlist(
    playlist_id: int, payload: PlaylistUpdate, session: Session = Depends(get_session)
) -> Playlist:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "playlist not found")
    updates = payload.model_dump(exclude_unset=True)
    _validate(updates.get("mode"), updates.get("advance_trigger"))
    if updates.get("entries") is not None:
        updates["entries"] = [dict(e) for e in updates["entries"]]

    if updates.get("active"):
        others = session.exec(select(Playlist).where(Playlist.id != playlist_id)).all()
        for other in others:
            if other.active:
                other.active = False
                session.add(other)

    for key, value in updates.items():
        setattr(playlist, key, value)
    session.add(playlist)
    session.commit()
    session.refresh(playlist)
    return playlist


@router.delete("/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: int, session: Session = Depends(get_session)) -> None:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "playlist not found")
    session.delete(playlist)
    session.commit()


@router.post("/{playlist_id}/activate", response_model=PlaylistRead)
def activate_playlist(
    playlist_id: int, session: Session = Depends(get_session)
) -> Playlist:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "playlist not found")
    others = session.exec(select(Playlist).where(Playlist.id != playlist_id)).all()
    for other in others:
        if other.active:
            other.active = False
            session.add(other)
    playlist.active = True
    session.add(playlist)
    session.commit()
    session.refresh(playlist)
    return playlist


@router.post("/{playlist_id}/next", response_model=PlaylistStatus)
def playlist_next(
    playlist_id: int, session: Session = Depends(get_session)
) -> PlaylistStatus:
    return _manual_advance(playlist_id, 1, session)


@router.post("/{playlist_id}/prev", response_model=PlaylistStatus)
def playlist_prev(
    playlist_id: int, session: Session = Depends(get_session)
) -> PlaylistStatus:
    return _manual_advance(playlist_id, -1, session)


def _manual_advance(playlist_id: int, delta: int, session: Session) -> PlaylistStatus:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "playlist not found")

    runner = engine.playlist_runner()
    if runner is not None:
        return runner.advance(delta)

    # No render loop (e.g. tests): do the index math + scene activation inline.
    # Current position is inferred from whichever scene is active right now.
    scene_ids = [int(e["scene_id"]) for e in (playlist.entries or []) if "scene_id" in e]
    if not scene_ids:
        return PlaylistStatus(playlist_id=playlist.id)
    count = len(scene_ids)
    active = session.exec(select(Scene).where(Scene.active)).first()
    index = (
        scene_ids.index(active.id)
        if active is not None and active.id in scene_ids
        else 0
    )
    new_index, scene_id, _dir = step_playlist(
        session, scene_ids, playlist.mode, index, delta
    )
    next_index, _ = compute_next_index(playlist.mode, new_index, count, 1)
    return PlaylistStatus(
        playlist_id=playlist.id,
        index=new_index,
        scene_id=scene_id,
        next_scene_id=scene_ids[next_index],
    )


@phrase_router.get("/phrase", response_model=PhraseClockState)
def phrase_clock_state() -> PhraseClockState:
    return engine.phrase_clock_state()
