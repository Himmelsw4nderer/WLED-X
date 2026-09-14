"""Every seeded example graph must actually evaluate: no unknown node types,
no dangling sockets that break the executor, no all-black output under normal
signal, and every exposed console param must point at a real node + param key.
These graphs are hand-written dicts, so a typo'd handle wouldn't surface until
someone opened the effect in the editor -- this catches it at CI time instead.
"""

import numpy as np
import pytest

from wled_x.audio.analysis import NUM_BANDS, AudioFrame
from wled_x.effects.graph import EvalContext, evaluate_graph
from wled_x.effects.nodes import NODE_REGISTRY
from wled_x.examples import EXAMPLE_EFFECTS

_IDS = [effect.name for effect in EXAMPLE_EFFECTS]


def _context(n: int, time: float) -> EvalContext:
    # Mid-strength audio on every band plus some hype, so audio-gated effects
    # (Bass Pulse, Ripple, Twinkle, Hype Strobe) actually light up.
    audio = AudioFrame(
        level=0.6,
        bands=np.full(NUM_BANDS, 0.5, dtype=np.float32),
        low=0.6,
        mid=0.5,
        high=0.7,
        beat=1.0,
        bpm=128.0,
        beat_phase=(time * 2.0) % 1.0,
    )
    positions = np.stack(
        [np.linspace(0.0, 3.0, n), np.full(n, 1.1), np.zeros(n)], axis=1
    ).astype(np.float32)
    return EvalContext(n=n, positions=positions, time=time, audio=audio, hype=0.8)


@pytest.mark.parametrize("effect", EXAMPLE_EFFECTS, ids=_IDS)
def test_example_graph_evaluates_to_a_valid_color_buffer(effect):
    n = 30
    state: dict = {}
    for frame in range(10):
        context = _context(n, time=frame * 0.1)
        context.state = state
        colors, _ = evaluate_graph(effect.graph, NODE_REGISTRY, context)
        assert colors.shape == (n, 3)
        assert np.all(np.isfinite(colors))


@pytest.mark.parametrize("effect", EXAMPLE_EFFECTS, ids=_IDS)
def test_example_graph_lights_up_within_a_second(effect):
    # Strobes and beat-stepped effects can be dark on any single frame, so sample
    # a second of animation and require at least one frame with real output.
    n = 30
    state: dict = {}
    brightest = 0.0
    for frame in range(60):
        context = _context(n, time=frame / 60.0)
        context.state = state
        colors, _ = evaluate_graph(effect.graph, NODE_REGISTRY, context)
        brightest = max(brightest, float(colors.max()))
    assert brightest > 0.05, f"{effect.name!r} never rises above near-black"


@pytest.mark.parametrize("effect", EXAMPLE_EFFECTS, ids=_IDS)
def test_exposed_params_point_at_real_nodes_and_param_keys(effect):
    nodes_by_id = {node["id"]: node for node in effect.graph["nodes"]}
    for exposed in effect.exposed_params:
        node = nodes_by_id.get(exposed["node_id"])
        assert node is not None, f"{effect.name}: exposes unknown node {exposed['node_id']!r}"
        definition = NODE_REGISTRY[node["type"]]
        param_keys = {param.key for param in definition.descriptor.params}
        assert exposed["param_key"] in param_keys, (
            f"{effect.name}: node {exposed['node_id']!r} ({node['type']}) has no param "
            f"{exposed['param_key']!r}"
        )
