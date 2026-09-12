"""Node graph model + vectorized numpy executor.

Mirrors `Effect.graph` exactly: {"nodes": [{"id","type","position","data"}],
"edges": [{"id","source","sourceHandle","target","targetHandle"}]}. A value
flowing through the graph is one of: `float` ("scalar"), `np.ndarray` shape
`(N,)` ("field"), or `np.ndarray` shape `(N, 3)` ("color"), where N is the LED
count of whichever single fixture is being evaluated -- one `evaluate_graph`
call renders one fixture; callers loop over fixtures.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from wled_x.api.schemas import NodeTypeDescriptor
from wled_x.audio.analysis import AudioFrame

Value = float | np.ndarray


class GraphError(ValueError):
    pass


@dataclass
class EvalContext:
    n: int
    positions: np.ndarray  # (N, 3) meters, fixture-local
    time: float
    audio: AudioFrame
    hype: float
    node_id: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    # Every currently-running audio source, keyed by name (e.g. "desktop",
    # "mic"), so nodes with a Source param can read one specifically. `audio`
    # above is always audio_sources["desktop"] when that source is running --
    # kept as its own field so every existing node that doesn't care about
    # multi-source audio never has to look this up.
    audio_sources: dict[str, AudioFrame] = field(default_factory=dict)
    # (min, max) meters across every fixture in the scene, for normalizing
    # PositionX/Y/Z to 0..1 across the whole installation. None falls back to
    # this fixture's own position range (e.g. the debug preview's synthetic strip,
    # which has no wider "scene" to normalize against).
    scene_bounds: tuple[np.ndarray, np.ndarray] | None = None


ComputeFn = Callable[[dict[str, Any], dict[str, Value], EvalContext], "Value | dict[str, Value]"]


@dataclass
class NodeDefinition:
    descriptor: NodeTypeDescriptor
    compute: ComputeFn


def evaluate_graph(
    graph: dict[str, Any],
    registry: dict[str, NodeDefinition],
    context: EvalContext,
    param_overrides: dict[tuple[str, str], float | str] | None = None,
) -> tuple[np.ndarray, dict[str, dict[str, Value]]]:
    """Returns (led colors, per-node output values) -- the latter is the raw
    `outputs` map keyed by node id then output socket key, used both to drive
    the final LedColor node and to power the effect editor's debug view (see
    api/routes_preview.py), which needs to see what every node produced, not
    just the final color."""
    nodes_list: list[dict[str, Any]] = graph.get("nodes", [])
    edges: list[dict[str, Any]] = graph.get("edges", [])
    nodes = {node["id"]: node for node in nodes_list}

    order = _topo_sort(nodes, edges)

    incoming_by_target: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        incoming_by_target.setdefault(edge["target"], []).append(edge)

    overrides = param_overrides or {}
    outputs: dict[str, dict[str, Value]] = {}

    for node_id in order:
        node = nodes[node_id]
        definition = registry.get(node.get("type", ""))
        if definition is None:
            raise GraphError(f"unknown node type {node.get('type')!r} for node {node_id!r}")

        node_data = dict(node.get("data") or {})
        for (override_node_id, param_key), value in overrides.items():
            if override_node_id == node_id:
                node_data[param_key] = value

        node_params = {param.key: param for param in definition.descriptor.params}
        resolved_inputs: dict[str, Value] = {}
        for socket in definition.descriptor.inputs:
            candidate_edges = incoming_by_target.get(node_id, [])
            edge = next(
                (e for e in candidate_edges if e.get("targetHandle") == socket.key),
                None,
            )
            if edge is not None and edge["source"] in outputs:
                resolved_inputs[socket.key] = _resolve_source_value(
                    outputs[edge["source"]], edge.get("sourceHandle")
                )
            elif socket.key in node_data:
                resolved_inputs[socket.key] = node_data[socket.key]
            elif socket.key in node_params:
                # No edge and no explicit data -- fall back to the node type's
                # declared param default (e.g. RGB's r/g/b default to 1.0, not
                # 0.0) rather than a blanket zero for every socket type.
                resolved_inputs[socket.key] = node_params[socket.key].default
            else:
                resolved_inputs[socket.key] = _default_for_socket(socket.type, context.n)

        node_context = replace(context, node_id=node_id)
        raw = definition.compute(node_data, resolved_inputs, node_context)
        if isinstance(raw, dict):
            outputs[node_id] = raw
        else:
            outputs_declared = definition.descriptor.outputs
            out_key = outputs_declared[0].key if outputs_declared else "value"
            outputs[node_id] = {out_key: raw}

    led_color_node = next((n for n in nodes_list if n.get("type") == "led_color"), None)
    if led_color_node is None or led_color_node["id"] not in outputs:
        return np.zeros((context.n, 3), dtype=np.float32), outputs

    result = _resolve_source_value(outputs[led_color_node["id"]], None)
    return _broadcast_color(result, context.n), outputs


def _topo_sort(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    # Both keyed by node id and deduplicated by set, not list: a node can
    # legitimately have several edges to the same downstream node (e.g. one
    # field wired into all three of an RGB node's r/g/b inputs), and counting
    # each such edge separately here would re-queue the successor once per
    # edge instead of once per node, corrupting the sort.
    incoming: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src not in nodes or tgt not in nodes:
            continue
        incoming[tgt].add(src)
        outgoing[src].add(tgt)

    ready = sorted(node_id for node_id, deps in incoming.items() if not deps)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for successor in sorted(outgoing[node_id]):
            incoming[successor].discard(node_id)
            if not incoming[successor]:
                ready.append(successor)

    if len(order) != len(nodes):
        remaining = sorted(set(nodes) - set(order))
        raise GraphError(f"effect graph has a cycle involving node(s): {remaining}")
    return order


def _resolve_source_value(outputs_for_node: dict[str, Value], handle: str | None) -> Value:
    if handle and handle in outputs_for_node:
        return outputs_for_node[handle]
    if len(outputs_for_node) == 1:
        return next(iter(outputs_for_node.values()))
    if handle is None:
        raise GraphError("ambiguous edge: source node has multiple outputs and no sourceHandle")
    raise GraphError(f"unknown output socket {handle!r}")


def _default_for_socket(socket_type: str, n: int) -> Value:
    if socket_type == "scalar":
        return 0.0
    if socket_type == "field":
        return np.zeros(n, dtype=np.float32)
    # "vec3" is a per-LED spatial vector -- same (N, 3) shape as "color", but
    # kept as its own type so the editor won't let you wire a position into a
    # color slot (or vice versa).
    if socket_type in ("color", "vec3"):
        return np.zeros((n, 3), dtype=np.float32)
    raise GraphError(f"unknown socket type {socket_type!r}")


def _broadcast_color(value: Value, n: int) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.shape == (n, 3):
        return arr
    if arr.shape == (3,):
        return np.tile(arr, (n, 1))
    if arr.ndim == 0:
        return np.tile(arr, (n, 3))
    raise GraphError(f"LedColor output has unexpected shape {arr.shape}, expected ({n}, 3)")
