"""Pydantic request/response DTOs. Kept separate from the SQLModel table models
so DB schema changes don't silently change the wire format."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from lumen.models.device import DeviceSource

Point3 = tuple[float, float, float]


class DeviceRead(BaseModel):
    id: int
    name: str
    ip: str
    mac: str | None
    led_count: int
    source: DeviceSource
    online: bool
    last_seen: datetime | None


class DeviceCreate(BaseModel):
    name: str
    ip: str
    mac: str | None = None
    led_count: int = 0
    source: DeviceSource = DeviceSource.MANUAL


class DeviceUpdate(BaseModel):
    name: str | None = None
    led_count: int | None = None


class FixtureRead(BaseModel):
    id: int
    name: str
    device_id: int
    start_channel: int
    led_count: int
    points: list[Point3]


class FixtureCreate(BaseModel):
    name: str
    device_id: int
    start_channel: int = 0
    led_count: int
    points: list[Point3]


class FixtureUpdate(BaseModel):
    name: str | None = None
    start_channel: int | None = None
    led_count: int | None = None
    points: list[Point3] | None = None


class ExposedParam(BaseModel):
    node_id: str
    param_key: str
    label: str
    min: float = 0.0
    max: float = 1.0
    default: float = 0.0


class EffectRead(BaseModel):
    id: int
    name: str
    description: str
    graph: dict[str, Any]
    exposed_params: list[ExposedParam]
    updated_at: datetime


class EffectCreate(BaseModel):
    name: str
    description: str = ""
    graph: dict[str, Any] = {"nodes": [], "edges": []}
    exposed_params: list[ExposedParam] = []


class EffectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: dict[str, Any] | None = None
    exposed_params: list[ExposedParam] | None = None


class SceneAssignment(BaseModel):
    fixture_ids: list[int] | str  # explicit ids, or "all"
    effect_id: int
    params: dict[str, float] = {}
    brightness: float = 1.0


class SceneRead(BaseModel):
    id: int
    name: str
    assignments: list[SceneAssignment]
    active: bool


class SceneCreate(BaseModel):
    name: str
    assignments: list[SceneAssignment] = []


class SceneUpdate(BaseModel):
    name: str | None = None
    assignments: list[SceneAssignment] | None = None
    active: bool | None = None


class NodeSocket(BaseModel):
    key: str
    type: str  # "scalar" | "field" | "color"
    label: str = ""


class NodeParam(BaseModel):
    key: str
    type: str  # "float" | "int" | "color" | "select"
    default: Any = 0.0
    min: float | None = None
    max: float | None = None
    options: list[str] | None = None


class NodeTypeDescriptor(BaseModel):
    type: str
    category: str
    label: str
    inputs: list[NodeSocket] = []
    outputs: list[NodeSocket] = []
    params: list[NodeParam] = []


class ConsoleState(BaseModel):
    master_brightness: float = 1.0
    active_scene_id: int | None = None
    param_overrides: dict[str, float] = {}
    hype: float = 0.0


class PreviewRequest(BaseModel):
    graph: dict[str, Any]
    led_count: int = 30
    param_overrides: dict[str, float] = {}


class NodePreview(BaseModel):
    socket_type: str  # "scalar" | "field" | "color"
    # scalar: length-1 list; field: one float per LED; color: one [r,g,b] (0-255) per LED.
    values: list[Any]


class PreviewResponse(BaseModel):
    colors: list[list[int]]
    nodes: dict[str, NodePreview]
    warning: str | None = None
