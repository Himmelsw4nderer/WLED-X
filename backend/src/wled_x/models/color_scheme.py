from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ColorScheme(SQLModel, table=True):
    """A saved palette of RGB colors (0..1 floats each) that effect graphs can
    pull from via the Scheme Color / Scheme Random Color nodes instead of a
    hardcoded hue -- flip the console's active scheme and every effect built
    on it re-colors together, without touching a single graph.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    colors: list[list[float]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
