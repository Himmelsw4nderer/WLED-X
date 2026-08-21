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
