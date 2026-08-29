from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

Point3 = tuple[float, float, float]


class Fixture(SQLModel, table=True):
    """A named run of LEDs mapped onto a Device's pixel buffer and positioned in 3D.

    `points` is a polyline (>=2 control points, in meters) that the fixture's
    `led_count` LEDs are distributed along by arc length. Two points describe a
    straight strip; more points describe a bent/curved run.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    device_id: int = Field(foreign_key="device.id", index=True)
    start_channel: int = 0
    led_count: int = 1
    points: list[Point3] = Field(default_factory=list, sa_column=Column(JSON))
    reverse: bool = False
    """Flip LED order along the path -- LED 0 sits at `points[-1]` instead of
    `points[0]`. Fixes a strip whose physical wiring runs opposite to however
    its path was drawn, without needing to redraw the path itself."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
