from wled_x.effects.graph import NodeDefinition
from wled_x.effects.nodes.audio_nodes import AUDIO_NODES
from wled_x.effects.nodes.color_nodes import COLOR_NODES
from wled_x.effects.nodes.math_nodes import MATH_NODES
from wled_x.effects.nodes.spatial_nodes import SPATIAL_NODES
from wled_x.effects.nodes.time_nodes import TIME_NODES

NODE_REGISTRY: dict[str, NodeDefinition] = {
    **SPATIAL_NODES,
    **TIME_NODES,
    **AUDIO_NODES,
    **MATH_NODES,
    **COLOR_NODES,
}

__all__ = ["NODE_REGISTRY"]
