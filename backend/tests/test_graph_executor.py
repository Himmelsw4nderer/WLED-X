import numpy as np
import pytest

from lumen.audio.analysis import NUM_BANDS, AudioFrame
from lumen.effects.graph import EvalContext, GraphError, evaluate_graph
from lumen.effects.nodes import NODE_REGISTRY


def _context(n: int = 4) -> EvalContext:
    positions = np.zeros((n, 3), dtype=np.float32)
    audio = AudioFrame(
        level=0.0, bands=np.zeros(NUM_BANDS, dtype=np.float32), low=0.0, mid=0.0, high=0.0, beat=0.0
    )
    return EvalContext(n=n, positions=positions, time=0.0, audio=audio, hype=0.0)


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
    result = evaluate_graph(graph, NODE_REGISTRY, _context(4))
    assert result.shape == (4, 3)
    assert np.allclose(result, 0.5)


def test_missing_led_color_node_yields_black():
    graph = {"nodes": [{"id": "c1", "type": "constant", "data": {"value": 1.0}}], "edges": []}
    result = evaluate_graph(graph, NODE_REGISTRY, _context(3))
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
    result = evaluate_graph(graph, NODE_REGISTRY, _context(5))
    assert result.shape == (5, 3)
    # hue wraps (h=0 and h=1 are both red), so compare against the midpoint instead
    assert not np.allclose(result[0], result[2])


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
    result = evaluate_graph(graph, NODE_REGISTRY, _context(4))
    assert result.shape == (4, 3)
