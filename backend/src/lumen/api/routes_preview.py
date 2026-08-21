"""Live preview for the effect editor's debug mode: evaluates a graph (saved
or not) against a synthetic straight strip and returns both the final LED
colors and every node's raw output, so the editor can show what each node is
actually producing instead of the user having to guess from a dark strip.
"""

import numpy as np
from fastapi import APIRouter, HTTPException

from lumen.api.schemas import NodePreview, PreviewRequest, PreviewResponse
from lumen.console.state import console
from lumen.effects import engine
from lumen.effects.geometry import led_positions
from lumen.effects.graph import EvalContext, GraphError, evaluate_graph
from lumen.effects.nodes import NODE_REGISTRY

router = APIRouter(prefix="/api/effects", tags=["effects"])

MAX_PREVIEW_LEDS = 300
MAX_PREVIEW_LENGTH_METERS = 1000.0


@router.post("/preview", response_model=PreviewResponse)
def preview_effect(payload: PreviewRequest) -> PreviewResponse:
    led_count = max(1, min(payload.led_count, MAX_PREVIEW_LEDS))
    length = max(0.01, min(payload.length_meters, MAX_PREVIEW_LENGTH_METERS))
    positions = led_positions([(0.0, 0.0, 0.0), (length, 0.0, 0.0)], led_count)

    overrides: dict[tuple[str, str], float] = {}
    for key, value in payload.param_overrides.items():
        node_id, _, param_key = key.rpartition(":")
        if node_id:
            overrides[(node_id, param_key)] = value

    context = EvalContext(
        n=led_count,
        positions=positions,
        time=engine.elapsed_time(),
        audio=engine.live_audio(),
        hype=console.snapshot().hype,
    )

    try:
        colors, node_outputs = evaluate_graph(payload.graph, NODE_REGISTRY, context, overrides)
    except GraphError as exc:
        raise HTTPException(422, str(exc)) from exc

    node_types = {node["id"]: node.get("type") for node in payload.graph.get("nodes", [])}
    nodes_preview = {
        node_id: _summarize(node_types.get(node_id), sockets)
        for node_id, sockets in node_outputs.items()
    }

    colors_u8 = np.clip(colors, 0.0, 1.0) * 255.0
    colors_list = colors_u8.astype(np.uint8).tolist()

    # The LedColor node's raw stored output isn't broadcast to one row per LED
    # until the step above -- show the real final per-LED colors for it
    # rather than whatever (possibly unbroadcast) value it happened to store.
    led_color_id = next(
        (n["id"] for n in payload.graph.get("nodes", []) if n.get("type") == "led_color"), None
    )
    if led_color_id is not None:
        nodes_preview[led_color_id] = NodePreview(socket_type="color", values=colors_list)

    warning = None
    if colors_u8.size and colors_u8.max() < 1.0:
        warning = "Every LED is black -- check what's feeding the LED Color node's input."

    return PreviewResponse(colors=colors_list, nodes=nodes_preview, warning=warning)


def _summarize(node_type: str | None, sockets: dict[str, object]) -> NodePreview:
    definition = NODE_REGISTRY.get(node_type or "")
    outputs = definition.descriptor.outputs if definition else []
    out_key = outputs[0].key if outputs else None
    value = sockets.get(out_key) if out_key else next(iter(sockets.values()), 0.0)

    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 0:
        return NodePreview(socket_type="scalar", values=[float(arr)])
    if arr.ndim == 1:
        return NodePreview(socket_type="field", values=[round(float(v), 4) for v in arr])
    rgb = np.clip(arr, 0.0, 1.0) * 255.0
    return NodePreview(socket_type="color", values=rgb.astype(np.uint8).tolist())
