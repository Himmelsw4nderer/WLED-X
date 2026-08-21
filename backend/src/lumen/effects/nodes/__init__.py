from lumen.effects.graph import NodeDefinition
from lumen.effects.nodes.audio_nodes import AUDIO_NODES
from lumen.effects.nodes.color_nodes import COLOR_NODES
from lumen.effects.nodes.math_nodes import MATH_NODES
from lumen.effects.nodes.spatial_nodes import SPATIAL_NODES
from lumen.effects.nodes.time_nodes import TIME_NODES

NODE_REGISTRY: dict[str, NodeDefinition] = {
    **SPATIAL_NODES,
    **TIME_NODES,
    **AUDIO_NODES,
    **MATH_NODES,
    **COLOR_NODES,
}

__all__ = ["NODE_REGISTRY"]
