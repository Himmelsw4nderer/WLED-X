from fastapi import APIRouter

from lumen.api.schemas import NodeTypeDescriptor
from lumen.effects.nodes import NODE_REGISTRY

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeTypeDescriptor])
def list_node_types() -> list[NodeTypeDescriptor]:
    return [definition.descriptor for definition in NODE_REGISTRY.values()]
