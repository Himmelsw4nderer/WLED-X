def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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
