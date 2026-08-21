import numpy as np
import pytest

from lumen.audio.analysis import NUM_BANDS, AudioFrame
from lumen.effects.graph import EvalContext, GraphError, evaluate_graph
from lumen.effects.nodes import NODE_REGISTRY


def _context(n: int = 4, positions: np.ndarray | None = None, scene_bounds=None) -> EvalContext:
    if positions is None:
        positions = np.zeros((n, 3), dtype=np.float32)
    audio = AudioFrame(
        level=0.0, bands=np.zeros(NUM_BANDS, dtype=np.float32), low=0.0, mid=0.0, high=0.0, beat=0.0
    )
    return EvalContext(
        n=n, positions=positions, time=0.0, audio=audio, hype=0.0, scene_bounds=scene_bounds
    )


def test_position_x_normalizes_against_scene_bounds_not_fixture_bounds():
    graph = {"nodes": [{"id": "px", "type": "position_x", "data": {}}], "edges": []}
    # This fixture only spans x in [4, 6], but the room (scene_bounds) spans [0, 10] --
    # PositionX should read against the room, not just this one strip's own extent.
    positions = np.array([[4.0, 0.0, 0.0], [5.0, 0.0, 0.0], [6.0, 0.0, 0.0]], dtype=np.float32)
    scene_bounds = (np.array([0.0, 0.0, 0.0]), np.array([10.0, 0.0, 0.0]))
    _, outputs = evaluate_graph(
        graph, NODE_REGISTRY, _context(3, positions=positions, scene_bounds=scene_bounds)
    )
    assert np.allclose(outputs["px"]["value"], [0.4, 0.5, 0.6])


def test_position_x_falls_back_to_fixture_bounds_without_a_scene():
    graph = {"nodes": [{"id": "px", "type": "position_x", "data": {}}], "edges": []}
    positions = np.array([[4.0, 0.0, 0.0], [5.0, 0.0, 0.0], [6.0, 0.0, 0.0]], dtype=np.float32)
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(3, positions=positions))
    assert np.allclose(outputs["px"]["value"], [0.0, 0.5, 1.0])


def test_position_axis_is_zero_for_a_degenerate_range():
    graph = {"nodes": [{"id": "py", "type": "position_y", "data": {}}], "edges": []}
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(3))
    assert np.allclose(outputs["py"]["value"], 0.0)


def test_global_axis_returns_raw_meters_unlike_normalized_position():
    graph = {
        "nodes": [
            {"id": "px", "type": "position_x", "data": {}},
            {"id": "gx", "type": "global_x", "data": {}},
        ],
        "edges": [],
    }
    positions = np.array([[4.0, 0.0, 0.0], [5.0, 0.0, 0.0], [6.0, 0.0, 0.0]], dtype=np.float32)
    scene_bounds = (np.array([0.0, 0.0, 0.0]), np.array([10.0, 0.0, 0.0]))
    _, outputs = evaluate_graph(
        graph, NODE_REGISTRY, _context(3, positions=positions, scene_bounds=scene_bounds)
    )
    # Normalized against the wider scene...
    assert np.allclose(outputs["px"]["value"], [0.4, 0.5, 0.6])
    # ...but the raw meter positions are unaffected by scene_bounds entirely.
    assert np.allclose(outputs["gx"]["value"], [4.0, 5.0, 6.0])


def test_one_source_feeding_multiple_sockets_on_the_same_node_is_not_a_cycle():
    # Regression test: wiring one output into several input sockets of the same
    # downstream node (e.g. one field into RGB's r, g, and b) used to corrupt the
    # topological sort -- outgoing edges were tracked as a list, so the successor
    # got re-queued once per duplicate edge, producing more entries in `order`
    # than there are nodes, which was misreported as "a cycle".
    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.4}},
            {"id": "rgb", "type": "rgb", "data": {}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "c1", "target": "rgb", "targetHandle": "r"},
            {"id": "e2", "source": "c1", "target": "rgb", "targetHandle": "g"},
            {"id": "e3", "source": "c1", "target": "rgb", "targetHandle": "b"},
            {"id": "e4", "source": "rgb", "target": "out", "targetHandle": "color"},
        ],
    }
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(3))
    assert np.allclose(result, 0.4)


def test_constant_to_led_color_yields_solid_color():
    graph = {
        "nodes": [
            {"id": "c1", "type": "constant", "data": {"value": 0.5}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "c1",
                "sourceHandle": "value",
                "target": "out",
                "targetHandle": "color",
            },
        ],
    }
    result, node_outputs = evaluate_graph(graph, NODE_REGISTRY, _context(4))
    assert result.shape == (4, 3)
    assert np.allclose(result, 0.5)
    assert node_outputs["c1"]["value"] == 0.5


def test_missing_led_color_node_yields_black():
    graph = {"nodes": [{"id": "c1", "type": "constant", "data": {"value": 1.0}}], "edges": []}
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(3))
    assert result.shape == (3, 3)
    assert np.allclose(result, 0.0)


def test_hsv_field_position_produces_gradient():
    graph = {
        "nodes": [
            {"id": "idx", "type": "index_normalized", "data": {}},
            {"id": "hsv", "type": "hsv", "data": {"s": 1.0, "v": 1.0}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "idx", "target": "hsv", "targetHandle": "h"},
            {"id": "e2", "source": "hsv", "target": "out", "targetHandle": "color"},
        ],
    }
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(5))
    assert result.shape == (5, 3)
    # hue wraps (h=0 and h=1 are both red), so compare against the midpoint instead
    assert not np.allclose(result[0], result[2])


def test_rgb_node_yields_direct_color():
    graph = {
        "nodes": [
            {"id": "rgb", "type": "rgb", "data": {"r": 0.2, "g": 0.4, "b": 0.6}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [{"id": "e1", "source": "rgb", "target": "out", "targetHandle": "color"}],
    }
    result, node_outputs = evaluate_graph(graph, NODE_REGISTRY, _context(3))
    assert result.shape == (3, 3)
    assert np.allclose(result, [0.2, 0.4, 0.6])
    assert np.allclose(node_outputs["rgb"]["value"], [0.2, 0.4, 0.6])


def test_rgb_node_defaults_to_white():
    graph = {
        "nodes": [
            {"id": "rgb", "type": "rgb", "data": {}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [{"id": "e1", "source": "rgb", "target": "out", "targetHandle": "color"}],
    }
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(2))
    assert np.allclose(result, 1.0)


def test_rgb_node_accepts_per_channel_fields():
    graph = {
        "nodes": [
            {"id": "idx", "type": "index_normalized", "data": {}},
            {"id": "rgb", "type": "rgb", "data": {"g": 0.0, "b": 0.0}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "idx", "target": "rgb", "targetHandle": "r"},
            {"id": "e2", "source": "rgb", "target": "out", "targetHandle": "color"},
        ],
    }
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(4))
    assert np.allclose(result[:, 0], [0.0, 1 / 3, 2 / 3, 1.0])
    assert np.allclose(result[:, 1:], 0.0)


def test_cycle_is_rejected():
    graph = {
        "nodes": [
            {"id": "a", "type": "add", "data": {}},
            {"id": "b", "type": "add", "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "targetHandle": "a"},
            {"id": "e2", "source": "b", "target": "a", "targetHandle": "a"},
        ],
    }
    with pytest.raises(GraphError, match="cycle"):
        evaluate_graph(graph, NODE_REGISTRY, _context(2))


def test_unknown_node_type_raises():
    graph = {"nodes": [{"id": "x", "type": "nonexistent", "data": {}}], "edges": []}
    with pytest.raises(GraphError):
        evaluate_graph(graph, NODE_REGISTRY, _context(2))


def test_math_chain_produces_expected_field():
    graph = {
        "nodes": [
            {"id": "idx", "type": "index_normalized", "data": {}},
            {"id": "mul", "type": "multiply", "data": {"b": 2.0}},
            {"id": "hsv", "type": "hsv", "data": {"s": 0.0, "v": 1.0}},
            {"id": "out", "type": "led_color", "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "idx", "target": "mul", "targetHandle": "a"},
            {"id": "e2", "source": "mul", "target": "hsv", "targetHandle": "h"},
            {"id": "e3", "source": "hsv", "target": "out", "targetHandle": "color"},
        ],
    }
    result, _ = evaluate_graph(graph, NODE_REGISTRY, _context(4))
    assert result.shape == (4, 3)


def test_modulo_produces_a_sawtooth_ramp():
    # A continuously increasing value wrapped by Modulo is exactly a sawtooth:
    # it ramps up then snaps back to 0, unlike Sine's smooth curve.
    graph = {
        "nodes": [{"id": "mod", "type": "modulo", "data": {"value": 2.5, "divisor": 1.0}}],
        "edges": [],
    }
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
    assert np.allclose(outputs["mod"]["value"], 0.5)


def test_modulo_matches_numpy_mod_semantics_for_negative_values():
    graph = {
        "nodes": [{"id": "mod", "type": "modulo", "data": {"value": -0.3, "divisor": 1.0}}],
        "edges": [],
    }
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
    assert np.allclose(outputs["mod"]["value"], 0.7)


def test_modulo_with_zero_divisor_does_not_raise_or_produce_nan():
    graph = {
        "nodes": [{"id": "mod", "type": "modulo", "data": {"value": 5.0, "divisor": 0.0}}],
        "edges": [],
    }
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
    assert np.all(np.isfinite(outputs["mod"]["value"]))


def test_square_wave_is_hard_on_off_at_default_duty():
    graph = {"nodes": [{"id": "sq", "type": "square", "data": {"x": 0.0}}], "edges": []}
    cases = [(0.0, 1.0), (0.49, 1.0), (0.5, 0.0), (0.9, 0.0), (1.0, 1.0), (1.49, 1.0), (1.5, 0.0)]
    for x, expected in cases:
        graph["nodes"][0]["data"]["x"] = x
        _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
        assert outputs["sq"]["value"] == pytest.approx(expected), f"x={x}"


def test_square_wave_duty_cycle_controls_on_fraction():
    graph = {"nodes": [{"id": "sq", "type": "square", "data": {"duty": 0.25}}], "edges": []}
    cases = [(0.1, 1.0), (0.25, 0.0), (0.5, 0.0), (0.9, 0.0)]
    for x, expected in cases:
        graph["nodes"][0]["data"]["x"] = x
        _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
        assert outputs["sq"]["value"] == pytest.approx(expected), f"x={x}"


def test_invert_flips_a_value_around_its_midpoint():
    graph = {"nodes": [{"id": "inv", "type": "invert", "data": {"value": 0.3}}], "edges": []}
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
    assert outputs["inv"]["value"] == pytest.approx(0.7)


def test_invert_flips_square_waves_on_state():
    graph = {
        "nodes": [
            {"id": "sq", "type": "square", "data": {"x": 0.1}},
            {"id": "inv", "type": "invert", "data": {}},
        ],
        "edges": [{"id": "e1", "source": "sq", "target": "inv", "targetHandle": "value"}],
    }
    _, outputs = evaluate_graph(graph, NODE_REGISTRY, _context(1))
    assert outputs["sq"]["value"] == pytest.approx(1.0)
    assert outputs["inv"]["value"] == pytest.approx(0.0)
