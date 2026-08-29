from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Effect(SQLModel, table=True):
    """A node graph. `graph` is reactflow-shaped: {"nodes": [...], "edges": [...]}.

    Each node is {"id", "type", "position": {"x","y"}, "data": {<param key>: <value>}}.
    `exposed_params` lists which node params are surfaced as sliders in the
    editor's test panel and in the live console:
    [{"node_id", "param_key", "label", "min", "max", "default"}].
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    graph: dict[str, Any] = Field(
        default_factory=lambda: {"nodes": [], "edges": []}, sa_column=Column(JSON)
    )
    exposed_params: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
