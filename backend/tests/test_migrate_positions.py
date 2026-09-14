from wled_x.migrate_positions import migrate_graph


def test_migrate_rewrites_every_legacy_axis_node_and_keeps_other_data():
    graph = {
        "nodes": [
            {"id": "a", "type": "position_x", "data": {}, "position": {"x": 1, "y": 2}},
            {"id": "b", "type": "local_z", "data": {}},
            {"id": "c", "type": "global_y", "data": {}},
            {"id": "d", "type": "distance_from_origin", "data": {}},
            {"id": "e", "type": "index_normalized", "data": {}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [],
    }
    migrated, changed = migrate_graph(graph)
    assert changed == 4
    by_id = {n["id"]: n for n in migrated["nodes"]}
    assert by_id["a"]["type"] == "position"
    assert by_id["a"]["data"] == {"space": "scene", "axis": "x"}
    assert by_id["a"]["position"] == {"x": 1, "y": 2}  # untouched
    assert by_id["b"]["data"] == {"space": "local", "axis": "z"}
    assert by_id["c"]["data"] == {"space": "meters", "axis": "y"}
    assert by_id["d"]["data"] == {"space": "meters", "axis": "xyz"}
    assert by_id["e"]["type"] == "index_normalized"  # not a position node
    assert by_id["out"]["type"] == "led_color"


def test_migrate_is_idempotent():
    graph = {
        "nodes": [{"id": "a", "type": "position_x", "data": {}}],
        "edges": [],
    }
    once, first = migrate_graph(graph)
    twice, second = migrate_graph(once)
    assert first == 1
    assert second == 0
    assert twice["nodes"][0]["data"] == {"space": "scene", "axis": "x"}
