import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from lumen import db
from lumen.api.schemas import ConsoleState
from lumen.effects.phrase_clock import PhraseTick
from lumen.effects.playlist_runner import PlaylistRunner, compute_next_index
from lumen.models.playlist import Playlist
from lumen.models.scene import Scene

# --------------------------------------------------------------------------
# API tests -- use the shared `client` fixture (render loop disabled), so the
# next/prev routes exercise the inline DB fallback rather than a live runner.
# --------------------------------------------------------------------------


def test_playlist_crud_activate_and_transport(client):
    s1 = client.post("/api/scenes", json={"name": "A"}).json()
    s2 = client.post("/api/scenes", json={"name": "B"}).json()
    s3 = client.post("/api/scenes", json={"name": "C"}).json()

    r = client.post(
        "/api/playlists",
        json={
            "name": "Show",
            "entries": [{"scene_id": s1["id"]}, {"scene_id": s2["id"]}, {"scene_id": s3["id"]}],
            "advance_trigger": "manual",
        },
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert [e["scene_id"] for e in r.json()["entries"]] == [s1["id"], s2["id"], s3["id"]]

    # list
    assert [p["id"] for p in client.get("/api/playlists").json()] == [pid]

    # activate -> only this one active
    pid2 = client.post("/api/playlists", json={"name": "Other"}).json()["id"]
    assert client.post(f"/api/playlists/{pid2}/activate").json()["active"] is True
    assert client.post(f"/api/playlists/{pid}/activate").json()["active"] is True
    by_id = {p["id"]: p for p in client.get("/api/playlists").json()}
    assert by_id[pid]["active"] is True
    assert by_id[pid2]["active"] is False

    # patch entries (reorder)
    r = client.patch(
        f"/api/playlists/{pid}",
        json={"entries": [{"scene_id": s3["id"]}, {"scene_id": s1["id"]}]},
    )
    assert [e["scene_id"] for e in r.json()["entries"]] == [s3["id"], s1["id"]]

    # baseline: s3 active -> next wraps to s1, flipping Scene.active
    client.patch(f"/api/scenes/{s3['id']}", json={"active": True})
    st = client.post(f"/api/playlists/{pid}/next").json()
    assert st["index"] == 1
    assert st["scene_id"] == s1["id"]
    scenes = {s["id"]: s for s in client.get("/api/scenes").json()}
    assert scenes[s1["id"]]["active"] is True
    assert scenes[s3["id"]]["active"] is False

    # prev goes back to s3
    st = client.post(f"/api/playlists/{pid}/prev").json()
    assert st["index"] == 0
    assert st["scene_id"] == s3["id"]

    # deactivate all
    assert client.post("/api/playlists/deactivate").status_code == 204
    assert all(p["active"] is False for p in client.get("/api/playlists").json())

    # delete
    assert client.delete(f"/api/playlists/{pid}").status_code == 204
    assert client.get(f"/api/playlists/{pid}").status_code == 404
    assert client.delete(f"/api/playlists/{pid}").status_code == 404


def test_playlist_rejects_bad_mode_and_trigger(client):
    assert client.post("/api/playlists", json={"name": "x", "mode": "nope"}).status_code == 422
    assert (
        client.post("/api/playlists", json={"name": "x", "advance_trigger": "nope"}).status_code
        == 422
    )
    pid = client.post("/api/playlists", json={"name": "x"}).json()["id"]
    assert client.patch(f"/api/playlists/{pid}", json={"mode": "nope"}).status_code == 422


def test_status_and_phrase_endpoints(client):
    r = client.get("/api/playlists/status")
    assert r.status_code == 200
    assert r.json()["playlist_id"] is None

    r = client.get("/api/phrase")
    assert r.status_code == 200
    assert set(r.json()) >= {"bpm", "phrase_beat", "phrase_beats", "bar"}


# --------------------------------------------------------------------------
# PlaylistRunner unit tests -- point db.engine at an in-memory sqlite (same
# trick as test_engine.py's audio_db fixture) and drive synthetic ticks.
# --------------------------------------------------------------------------


@pytest.fixture
def playlist_db(monkeypatch):
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "engine", eng)
    return eng


def _seed(eng, n_scenes=3):
    with Session(eng) as s:
        for i in range(n_scenes):
            s.add(Scene(name=f"scene{i}", assignments=[]))
        s.commit()
        return [row.id for row in s.exec(select(Scene).order_by(Scene.id)).all()]


def _make_playlist(eng, scene_ids, **kw):
    with Session(eng) as s:
        pl = Playlist(
            name="p",
            active=True,
            entries=[{"scene_id": i} for i in scene_ids],
            **kw,
        )
        s.add(pl)
        s.commit()
        return pl.id


def _active_scene_id(eng):
    with Session(eng) as s:
        row = s.exec(select(Scene).where(Scene.active)).first()
        return row.id if row else None


async def test_first_tick_activates_entry_zero(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="manual")
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    assert _active_scene_id(playlist_db) == ids[0]


async def test_beats_trigger_advances_every_n(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="beats", advance_beats=4)
    runner = PlaylistRunner()
    cs = ConsoleState()
    await runner.tick(PhraseTick(), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[0]
    for _ in range(3):
        await runner.tick(PhraseTick(beat_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[0]
    await runner.tick(PhraseTick(beat_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[1]
    for _ in range(4):
        await runner.tick(PhraseTick(beat_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[2]


async def test_bars_trigger_advances_every_n_bars(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="bars", advance_beats=2)
    runner = PlaylistRunner()
    cs = ConsoleState()
    await runner.tick(PhraseTick(), None, cs, 0.0)
    await runner.tick(PhraseTick(beat_advanced=True, bar_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[0]
    await runner.tick(PhraseTick(beat_advanced=True, bar_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[1]


async def test_tempo_change_trigger(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="tempo_change")
    runner = PlaylistRunner()
    cs = ConsoleState()
    await runner.tick(PhraseTick(), None, cs, 0.0)
    await runner.tick(PhraseTick(beat_advanced=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[0]
    await runner.tick(PhraseTick(tempo_changed=True), None, cs, 0.0)
    assert _active_scene_id(playlist_db) == ids[1]


async def test_time_trigger(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="time", advance_seconds=10.0)
    runner = PlaylistRunner()
    cs = ConsoleState()
    await runner.tick(PhraseTick(), None, cs, 100.0)
    await runner.tick(PhraseTick(), None, cs, 105.0)
    assert _active_scene_id(playlist_db) == ids[0]
    await runner.tick(PhraseTick(), None, cs, 110.0)
    assert _active_scene_id(playlist_db) == ids[1]


async def test_hype_trigger_on_rising_edge(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="hype", hype_threshold=0.8)
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.0), 0.0)
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.5), 0.0)
    assert _active_scene_id(playlist_db) == ids[0]
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.9), 0.0)
    assert _active_scene_id(playlist_db) == ids[1]
    # stays high -> no repeat advance
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.95), 0.0)
    assert _active_scene_id(playlist_db) == ids[1]
    # drop then rise again -> advance
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.1), 0.0)
    await runner.tick(PhraseTick(), None, ConsoleState(hype=0.85), 0.0)
    assert _active_scene_id(playlist_db) == ids[2]


async def test_manual_advance_moves_index_and_active_scene(playlist_db):
    ids = _seed(playlist_db)
    _make_playlist(playlist_db, ids, advance_trigger="manual")
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    st = runner.advance(1)
    assert st.index == 1
    assert st.scene_id == ids[1]
    assert _active_scene_id(playlist_db) == ids[1]
    st = runner.advance(-1)
    assert st.index == 0
    assert _active_scene_id(playlist_db) == ids[0]


async def test_runner_skips_deleted_scene(playlist_db):
    ids = _seed(playlist_db, 3)
    _make_playlist(
        playlist_db,
        [ids[0], 9999, ids[2]],
        advance_trigger="manual",
        mode="sequential",
    )
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    st = runner.advance(1)
    assert st.index == 2
    assert _active_scene_id(playlist_db) == ids[2]


async def test_switching_active_playlist_resets_to_entry_zero(playlist_db):
    ids = _seed(playlist_db, 4)
    pid_a = _make_playlist(playlist_db, ids[:2], advance_trigger="manual")
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    runner.advance(1)
    assert _active_scene_id(playlist_db) == ids[1]

    with Session(playlist_db) as s:
        s.get(Playlist, pid_a).active = False
        s.add(Playlist(name="b", active=True, entries=[{"scene_id": ids[2]}, {"scene_id": ids[3]}]))
        s.commit()

    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    assert _active_scene_id(playlist_db) == ids[2]


async def test_empty_entries_is_noop(playlist_db):
    _seed(playlist_db, 2)
    _make_playlist(playlist_db, [], advance_trigger="beats", advance_beats=1)
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(beat_advanced=True), None, ConsoleState(), 0.0)
    assert _active_scene_id(playlist_db) is None


def test_compute_next_index_sequential():
    assert compute_next_index("sequential", 0, 3, 1)[0] == 1
    assert compute_next_index("sequential", 2, 3, 1)[0] == 0
    assert compute_next_index("sequential", 0, 3, -1)[0] == 2


def test_compute_next_index_pingpong_bounces():
    idx, d = 0, 1
    idx, d = compute_next_index("pingpong", idx, 3, 1, pingpong_dir=d)
    assert idx == 1
    idx, d = compute_next_index("pingpong", idx, 3, 1, pingpong_dir=d)
    assert idx == 2
    idx, d = compute_next_index("pingpong", idx, 3, 1, pingpong_dir=d)
    assert (idx, d) == (1, -1)
    idx, d = compute_next_index("pingpong", idx, 3, 1, pingpong_dir=d)
    assert idx == 0
    idx, d = compute_next_index("pingpong", idx, 3, 1, pingpong_dir=d)
    assert (idx, d) == (1, 1)


def test_compute_next_index_shuffle_never_repeats():
    for _ in range(100):
        nxt, _ = compute_next_index("shuffle", 3, 6, 1)
        assert nxt != 3
        assert 0 <= nxt < 6


async def test_pingpong_runner_end_to_end(playlist_db):
    ids = _seed(playlist_db, 3)
    _make_playlist(playlist_db, ids, advance_trigger="manual", mode="pingpong")
    runner = PlaylistRunner()
    await runner.tick(PhraseTick(), None, ConsoleState(), 0.0)
    assert [runner.advance(1).scene_id for _ in range(4)] == [
        ids[1],
        ids[2],
        ids[1],
        ids[0],
    ]
