from typing import Any

from wled_x.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from wled_x.effects.graph import EvalContext, NodeDefinition, Value


def _time(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    speed = float(data.get("speed", 1.0))
    return context.time * speed


TIME_NODES: dict[str, NodeDefinition] = {
    "time": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="time",
            category="time",
            label="Time",
            outputs=[NodeSocket(key="value", type="scalar", label="Time")],
            params=[NodeParam(key="speed", type="float", default=1.0, min=0.0, max=10.0)],
        ),
        compute=_time,
    ),
}
