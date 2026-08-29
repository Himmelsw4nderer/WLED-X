from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class DeviceSource(StrEnum):
    MDNS = "mdns"
    SCAN = "scan"
    MANUAL = "manual"


class Device(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    ip: str = Field(index=True, unique=True)
    mac: str | None = None
    led_count: int = 0
    source: DeviceSource = DeviceSource.MANUAL
    online: bool = False
    last_seen: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
