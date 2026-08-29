from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Scene(SQLModel, table=True):
    """One or more fixture-group -> effect assignments.

    `assignments`: [{"fixture_ids": [int, ...] | "all", "effect_id": int,
    "params": {<param_key>: <value>}, "brightness": 0..1}]
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    assignments: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
