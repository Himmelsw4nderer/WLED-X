"""Pydantic request/response DTOs. Kept separate from the SQLModel table models
so DB schema changes don't silently change the wire format."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from wled_x.models.device import DeviceSource

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
    reverse: bool


class FixtureCreate(BaseModel):
    name: str
    device_id: int
    start_channel: int = 0
    led_count: int
    points: list[Point3]
    reverse: bool = False


class FixtureUpdate(BaseModel):
    name: str | None = None
    device_id: int | None = None
    start_channel: int | None = None
    led_count: int | None = None
    points: list[Point3] | None = None
    reverse: bool | None = None


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
    type: str  # "scalar" | "field" | "color" | "vec3"
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
    # Which configured audio source ("desktop" / "mic" / ...) drives every
    # audio-reactive node and the phrase-clock. Chosen once here instead of
    # per node -- see wled_x.effects.nodes.audio_nodes.
    audio_source: str = "desktop"


class PhraseClockState(BaseModel):
    """Live snapshot of wled_x.effects.phrase_clock.PhraseClock, pushed over the
    WS as {"type": "phrase", ...} and returned by GET /api/phrase."""

    bpm: float = 0.0
    total_beats: int = 0
    phrase_beat: int = 0
    phrase_index: int = 0
    phrase_beats: int = 64
    bar: int = 0
    phrase_phase: float = 0.0


class PlaylistEntry(BaseModel):
    scene_id: int


class PlaylistRead(BaseModel):
    id: int
    name: str
    entries: list[PlaylistEntry]
    mode: str
    advance_trigger: str
    advance_beats: int
    advance_seconds: float
    hype_threshold: float
    active: bool


class PlaylistCreate(BaseModel):
    name: str
    entries: list[PlaylistEntry] = []
    mode: str = "sequential"
    advance_trigger: str = "beats"
    advance_beats: int = 32
    advance_seconds: float = 30.0
    hype_threshold: float = 0.8


class PlaylistUpdate(BaseModel):
    name: str | None = None
    entries: list[PlaylistEntry] | None = None
    mode: str | None = None
    advance_trigger: str | None = None
    advance_beats: int | None = None
    advance_seconds: float | None = None
    hype_threshold: float | None = None
    active: bool | None = None


class PlaylistStatus(BaseModel):
    """Where the active playlist is right now -- for the console panel."""

    playlist_id: int | None = None
    index: int = 0
    scene_id: int | None = None
    next_scene_id: int | None = None
    beats_until_advance: int | None = None
    seconds_until_advance: float | None = None


class AudioDeviceOption(BaseModel):
    """One selectable entry in the audio device picker -- see
    `wled_x.audio.capture.discover_audio_devices`."""

    id: str
    label: str
    mode: str
    device: str | None
    is_default: bool = False


class AudioSourceRead(BaseModel):
    name: str
    enabled: bool
    mode: str
    device: str | None


class AudioSourceUpdate(BaseModel):
    enabled: bool | None = None
    mode: str | None = None
    device: str | None = None


class PreviewRequest(BaseModel):
    graph: dict[str, Any]
    led_count: int = 30
    length_meters: float = 1.0
    param_overrides: dict[str, float] = {}


class NodePreview(BaseModel):
    socket_type: str  # "scalar" | "field" | "color" | "vec3"
    # scalar: length-1 list; field: one float per LED; color: one [r,g,b] (0-255)
    # per LED; vec3: one [x,y,z] (raw units) per LED.
    values: list[Any]


class PreviewResponse(BaseModel):
    colors: list[list[int]]
    nodes: dict[str, NodePreview]
    warning: str | None = None
