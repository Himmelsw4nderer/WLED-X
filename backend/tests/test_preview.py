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
