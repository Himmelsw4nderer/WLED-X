import pytest

from wled_x.api import routes_preview


def _edge(edge_id: str, source: str, target: str, target_handle: str) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": "value",
        "target": target,
        "targetHandle": target_handle,
    }


def test_preview_returns_colors_and_node_values(client):
    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.5}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [_edge("e1", "c1", "out", "color")],
    }
    resp = client.post("/api/effects/preview", json={"graph": graph, "led_count": 6})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["colors"]) == 6
    assert all(c == [127, 127, 127] for c in body["colors"])
    assert body["warning"] is None

    assert body["nodes"]["c1"]["socket_type"] == "scalar"
    assert body["nodes"]["c1"]["values"] == [0.5]
    assert body["nodes"]["out"]["socket_type"] == "color"
    assert len(body["nodes"]["out"]["values"]) == 6


def test_preview_flags_an_all_black_output(client):
    # Reproduces the exact bug this endpoint exists to catch: feeding a
    # constant-zero field (a flat fixture's Z position) into HSV's V input
    # silently renders every LED black.
    graph = {
        "nodes": [
            {"id": "pz", "type": "position_z", "data": {}},
            {"id": "hsv", "type": "hsv", "data": {"h": 0.0, "s": 1.0}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [_edge("e1", "pz", "hsv", "v"), _edge("e2", "hsv", "out", "color")],
    }
    resp = client.post("/api/effects/preview", json={"graph": graph, "led_count": 5})
    assert resp.status_code == 200
    body = resp.json()

    assert all(c == [0, 0, 0] for c in body["colors"])
    assert body["warning"] is not None
    assert "black" in body["warning"]
    # The Z field itself is right there in the response -- this is the value
    # a user would see and immediately recognize as "oh, that's always 0".
    assert body["nodes"]["pz"]["values"] == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_preview_applies_param_overrides(client):
    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.1}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [_edge("e1", "c1", "out", "color")],
    }
    resp = client.post(
        "/api/effects/preview",
        json={"graph": graph, "led_count": 2, "param_overrides": {"c1:value": 1.0}},
    )
    body = resp.json()
    assert body["colors"] == [[255, 255, 255], [255, 255, 255]]


def test_preview_rejects_a_cyclic_graph(client):
    graph = {
        "nodes": [{"id": "a", "type": "add", "data": {}}, {"id": "b", "type": "add", "data": {}}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "targetHandle": "a"},
            {"id": "e2", "source": "b", "target": "a", "targetHandle": "a"},
        ],
    }
    resp = client.post("/api/effects/preview", json={"graph": graph, "led_count": 3})
    assert resp.status_code == 422


def test_preview_caps_led_count(client):
    graph = {"nodes": [{"id": "out", "type": "led_color", "data": {}}], "edges": []}
    resp = client.post("/api/effects/preview", json={"graph": graph, "led_count": 10_000})
    assert resp.status_code == 200
    assert len(resp.json()["colors"]) == 300


def _preview_count(client, graph, trigger):
    resp = client.post(
        "/api/effects/preview",
        json={"graph": graph, "led_count": 3, "param_overrides": {"cnt:trigger": trigger}},
    )
    assert resp.status_code == 200
    return resp.json()["nodes"]["cnt"]["values"][0]


def test_preview_stateful_node_persists_across_polls(client):
    # The editor's debug preview is a series of independent HTTP requests; a
    # Counter must still accumulate across them instead of resetting 0->1->0
    # every poll.
    routes_preview._preview_state.clear()
    routes_preview._preview_signature = None

    graph = {
        "nodes": [
            {"id": "cnt", "type": "counter", "data": {"max": 8}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [],
    }
    assert _preview_count(client, graph, 0.0) == 0
    assert _preview_count(client, graph, 1.0) == 1  # rising edge across two requests
    assert _preview_count(client, graph, 1.0) == 1  # still high -> no re-trigger
    assert _preview_count(client, graph, 0.0) == 1  # re-arms
    assert _preview_count(client, graph, 1.0) == 2
    assert _preview_count(client, graph, 0.0) == 2

    # Adding a node changes the graph's node set -> persistent state is wiped.
    graph_plus = {
        "nodes": graph["nodes"] + [{"id": "k", "type": "constant", "data": {"value": 1.0}}],
        "edges": [],
    }
    assert _preview_count(client, graph_plus, 1.0) == 1  # fresh run


def test_preview_reports_vec3_socket_for_led_position(client):
    graph = {
        "nodes": [
            {"id": "p", "type": "led_position", "data": {}},
            {"id": "d", "type": "distance", "data": {"normalize": "radius_inv", "radius": 5.0}},
            {"id": "hsv", "type": "hsv", "data": {"s": 1.0}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "p",
                "sourceHandle": "position",
                "target": "d",
                "targetHandle": "a",
            },
            _edge("e2", "d", "hsv", "v"),
            _edge("e3", "hsv", "out", "color"),
        ],
    }
    resp = client.post(
        "/api/effects/preview", json={"graph": graph, "led_count": 4, "length_meters": 5.0}
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["nodes"]["p"]["socket_type"] == "vec3"
    assert len(body["nodes"]["p"]["values"]) == 4
    assert body["nodes"]["p"]["values"][0] == [0.0, 0.0, 0.0]
    # Distance still resolves to an ordinary 0..1 field the rest of the graph reads.
    assert body["nodes"]["d"]["socket_type"] == "field"
    assert body["nodes"]["d"]["values"][0] == pytest.approx(1.0)  # LED at the origin, radius_inv


def test_preview_length_meters_controls_global_x_but_not_position_x(client):
    # The debug strip defaults to exactly 1 meter, which makes Global X
    # (raw meters) numerically identical to Position X (0..1 normalized) --
    # indistinguishable in the tool meant to demonstrate the difference.
    # length_meters lets the user pick a more representative real distance.
    graph = {
        "nodes": [
            {"id": "px", "type": "position_x", "data": {}},
            {"id": "gx", "type": "global_x", "data": {}},
        ],
        "edges": [],
    }
    resp = client.post(
        "/api/effects/preview",
        json={"graph": graph, "led_count": 3, "length_meters": 5.0},
    )
    body = resp.json()
    assert body["nodes"]["px"]["values"] == [0.0, 0.5, 1.0]
    assert body["nodes"]["gx"]["values"] == [0.0, 2.5, 5.0]


def test_preview_room_with_no_fixtures_returns_empty_map_and_a_warning(client):
    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.5}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [_edge("e1", "c1", "out", "color")],
    }
    resp = client.post("/api/effects/preview_room", json={"graph": graph})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fixtures"] == {}
    assert body["warning"] is not None


def test_preview_room_evaluates_against_every_real_fixture(client):
    device = client.post("/api/devices", json={"name": "d", "ip": "10.0.0.20"}).json()
    fixture = client.post(
        "/api/fixtures",
        json={
            "name": "strip",
            "device_id": device["id"],
            "led_count": 3,
            "points": [[0, 0, 0], [1, 0, 0]],
        },
    ).json()

    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.5}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [_edge("e1", "c1", "out", "color")],
    }
    resp = client.post("/api/effects/preview_room", json={"graph": graph})
    assert resp.status_code == 200
    body = resp.json()
    assert body["warning"] is None
    assert set(body["fixtures"].keys()) == {str(fixture["id"])}
    assert len(body["fixtures"][str(fixture["id"])]) == 3
    assert all(c == [127, 127, 127] for c in body["fixtures"][str(fixture["id"])])


def test_preview_room_rejects_an_invalid_graph(client):
    graph = {
        "nodes": [{"id": "a", "type": "add", "data": {}}, {"id": "b", "type": "add", "data": {}}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "targetHandle": "a"},
            {"id": "e2", "source": "b", "target": "a", "targetHandle": "a"},
        ],
    }
    client.post("/api/devices", json={"name": "d2", "ip": "10.0.0.21"})
    device = client.get("/api/devices").json()[0]
    client.post(
        "/api/fixtures",
        json={
            "name": "s",
            "device_id": device["id"],
            "led_count": 2,
            "points": [[0, 0, 0], [1, 0, 0]],
        },
    )
    resp = client.post("/api/effects/preview_room", json={"graph": graph})
    assert resp.status_code == 422
