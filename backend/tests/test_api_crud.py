def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_audio_sources_are_seeded_with_desktop_enabled_and_mic_disabled(client):
    resp = client.get("/api/audio/sources")
    assert resp.status_code == 200
    by_name = {row["name"]: row for row in resp.json()}
    assert by_name["desktop"]["enabled"] is True
    assert by_name["desktop"]["mode"] == "loopback"
    assert by_name["mic"]["enabled"] is False
    assert by_name["mic"]["mode"] == "input"


def test_audio_devices_lists_discovered_options(client, monkeypatch):
    from wled_x.api import routes_audio

    async def fake_discover():
        return [
            {
                "id": "loopback:default",
                "label": "System audio",
                "mode": "loopback",
                "device": None,
                "is_default": True,
            },
            {
                "id": "input:0",
                "label": "USB Mic",
                "mode": "input",
                "device": "USB Mic",
                "is_default": False,
            },
        ]

    monkeypatch.setattr(routes_audio, "discover_audio_devices", fake_discover)
    resp = client.get("/api/audio/devices")
    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == ["loopback:default", "input:0"]


def test_put_audio_source_updates_device_and_rejects_unknown_name(client):
    resp = client.put("/api/audio/sources/mic", json={"enabled": True, "device": "USB Mic"})
    assert resp.status_code == 200
    assert resp.json() == {"name": "mic", "enabled": True, "mode": "input", "device": "USB Mic"}

    resp = client.get("/api/audio/sources")
    by_name = {row["name"]: row for row in resp.json()}
    assert by_name["mic"]["enabled"] is True
    assert by_name["mic"]["device"] == "USB Mic"

    resp = client.put("/api/audio/sources/nonexistent", json={"enabled": True})
    assert resp.status_code == 404


def test_device_crud(client):
    resp = client.post("/api/devices", json={"name": "Strip 1", "ip": "10.0.0.5", "led_count": 60})
    assert resp.status_code == 201
    device = resp.json()
    assert device["source"] == "manual"

    resp = client.post("/api/devices", json={"name": "dup", "ip": "10.0.0.5"})
    assert resp.status_code == 409

    resp = client.get("/api/devices")
    assert len(resp.json()) == 1

    resp = client.patch(f"/api/devices/{device['id']}", json={"name": "Renamed"})
    assert resp.json()["name"] == "Renamed"

    resp = client.delete(f"/api/devices/{device['id']}")
    assert resp.status_code == 204
    assert client.get("/api/devices").json() == []


def test_fixture_requires_two_points(client):
    device = client.post("/api/devices", json={"name": "d", "ip": "10.0.0.6"}).json()

    resp = client.post(
        "/api/fixtures",
        json={
            "name": "bad",
            "device_id": device["id"],
            "led_count": 10,
            "points": [[0, 0, 0]],
        },
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/fixtures",
        json={
            "name": "wall run",
            "device_id": device["id"],
            "led_count": 10,
            "points": [[0, 0, 0], [1, 0, 0]],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["led_count"] == 10


def test_fixture_reverse_defaults_false_and_can_be_toggled(client):
    device = client.post("/api/devices", json={"name": "d2", "ip": "10.0.0.7"}).json()
    fixture = client.post(
        "/api/fixtures",
        json={
            "name": "reversible",
            "device_id": device["id"],
            "led_count": 5,
            "points": [[0, 0, 0], [1, 0, 0]],
        },
    ).json()
    assert fixture["reverse"] is False

    resp = client.patch(f"/api/fixtures/{fixture['id']}", json={"reverse": True})
    assert resp.json()["reverse"] is True


def test_fixture_device_id_can_be_reassigned(client):
    # Regression test: PATCH /api/fixtures/{id} used to silently drop device_id
    # since it was missing from FixtureUpdate, so reassigning a fixture to a
    # different device never actually took effect.
    device_a = client.post("/api/devices", json={"name": "a", "ip": "10.0.0.10"}).json()
    device_b = client.post("/api/devices", json={"name": "b", "ip": "10.0.0.11"}).json()
    fixture = client.post(
        "/api/fixtures",
        json={
            "name": "movable",
            "device_id": device_a["id"],
            "led_count": 5,
            "points": [[0, 0, 0], [1, 0, 0]],
        },
    ).json()

    resp = client.patch(f"/api/fixtures/{fixture['id']}", json={"device_id": device_b["id"]})
    assert resp.status_code == 200
    assert resp.json()["device_id"] == device_b["id"]


def test_effect_and_scene_roundtrip(client):
    effect = client.post(
        "/api/effects",
        json={
            "name": "Pulse",
            "graph": {"nodes": [{"id": "n1", "type": "time"}], "edges": []},
            "exposed_params": [
                {
                    "node_id": "n1",
                    "param_key": "speed",
                    "label": "Speed",
                    "min": 0,
                    "max": 5,
                    "default": 1,
                }
            ],
        },
    ).json()
    assert effect["exposed_params"][0]["label"] == "Speed"

    scene = client.post(
        "/api/scenes",
        json={
            "name": "Show",
            "assignments": [{"fixture_ids": "all", "effect_id": effect["id"], "brightness": 0.8}],
        },
    ).json()
    assert scene["assignments"][0]["brightness"] == 0.8

    resp = client.patch(f"/api/scenes/{scene['id']}", json={"active": True})
    assert resp.json()["active"] is True


def test_scene_assignment_params_persist_fader_bank_values(client):
    # The console fader bank writes its values onto the scene's assignments,
    # keyed "{node_id}:{param_key}", floats for faders and strings for selects.
    effect = client.post(
        "/api/effects",
        json={"name": "P", "graph": {"nodes": [{"id": "n1", "type": "time"}], "edges": []}},
    ).json()
    scene = client.post(
        "/api/scenes",
        json={
            "name": "Ride",
            "assignments": [{"fixture_ids": "all", "effect_id": effect["id"], "brightness": 1.0}],
        },
    ).json()

    resp = client.patch(
        f"/api/scenes/{scene['id']}",
        json={
            "assignments": [
                {
                    "fixture_ids": "all",
                    "effect_id": effect["id"],
                    "brightness": 1.0,
                    "params": {"n1:speed": 2.5, "p1:axis": "y"},
                }
            ]
        },
    )
    assert resp.status_code == 200
    params = client.get(f"/api/scenes/{scene['id']}").json()["assignments"][0]["params"]
    assert params == {"n1:speed": 2.5, "p1:axis": "y"}


def test_effect_exposes_a_select_param_with_options_and_a_string_default(client):
    effect = client.post(
        "/api/effects",
        json={
            "name": "Axis Wipe",
            "graph": {
                "nodes": [{"id": "p", "type": "position", "data": {"space": "scene", "axis": "x"}}],
                "edges": [],
            },
            "exposed_params": [
                {
                    "node_id": "p",
                    "param_key": "axis",
                    "label": "Sweep Axis",
                    "options": ["x", "y", "z", "xz"],
                    "default": "x",
                }
            ],
        },
    ).json()

    exposed = effect["exposed_params"][0]
    assert exposed["options"] == ["x", "y", "z", "xz"]
    assert exposed["default"] == "x"

    # and it survives a read-back
    reread = client.get(f"/api/effects/{effect['id']}").json()["exposed_params"][0]
    assert reread["options"] == ["x", "y", "z", "xz"]
    assert reread["default"] == "x"


def test_duplicate_effect(client):
    graph = {
        "nodes": [
            {"id": "n1", "type": "time", "position": {"x": 0, "y": 0}, "data": {"speed": 1}},
            {"id": "n2", "type": "sine", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    }
    exposed = [
        {"node_id": "n1", "param_key": "speed", "label": "Speed", "min": 0, "max": 5, "default": 1}
    ]
    original = client.post(
        "/api/effects",
        json={"name": "Wave", "description": "a wave", "graph": graph, "exposed_params": exposed},
    ).json()

    resp = client.post(f"/api/effects/{original['id']}/duplicate")
    assert resp.status_code == 201
    copy1 = resp.json()
    assert copy1["id"] != original["id"]
    assert copy1["name"] == "Wave (copy)"
    assert copy1["graph"] == original["graph"]
    assert copy1["exposed_params"] == original["exposed_params"]

    resp = client.post(f"/api/effects/{original['id']}/duplicate")
    assert resp.status_code == 201
    assert resp.json()["name"] == "Wave (copy 2)"

    assert client.post("/api/effects/999999/duplicate").status_code == 404

    # Mutating the copy must not touch the original.
    mutated = dict(copy1["graph"])
    mutated["nodes"] = mutated["nodes"] + [{"id": "n3", "type": "out"}]
    resp = client.patch(f"/api/effects/{copy1['id']}", json={"graph": mutated})
    assert resp.status_code == 200
    assert len(resp.json()["graph"]["nodes"]) == 3
    assert len(client.get(f"/api/effects/{original['id']}").json()["graph"]["nodes"]) == 2
