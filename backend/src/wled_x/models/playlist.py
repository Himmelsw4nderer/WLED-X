from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

# What makes a playlist advance to its next entry.
#   "beats"        -- every `advance_beats` beats of the phrase-clock
#   "bars"         -- every `advance_beats` bars (bar = 4 beats)
#   "tempo_change" -- whenever the phrase-clock flags a significant BPM change
#   "time"         -- every `advance_seconds` wall-clock seconds
#   "hype"         -- each time console hype rises across `hype_threshold`
#   "manual"       -- only on an explicit next/prev call
ADVANCE_TRIGGERS = ("beats", "bars", "tempo_change", "time", "hype", "manual")

# How the next entry is chosen when the playlist advances.
PLAYLIST_MODES = ("sequential", "shuffle", "pingpong")


class Playlist(SQLModel, table=True):
    """An ordered list of scenes plus a rule for when to move to the next one,
    so a show can run itself off the beat instead of being clicked through by
    hand. Exactly one playlist is `active` at a time (same convention as
    `Scene.active`); the render loop's playlist runner watches the active one
    and flips `Scene.active` as it advances.

    `entries` is `[{"scene_id": int}]`, kept as JSON rather than a join table
    because order matters, the list is short, and it's always read whole.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    entries: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    mode: str = "sequential"
    advance_trigger: str = "beats"
    advance_beats: int = 32
    advance_seconds: float = 30.0
    hype_threshold: float = 0.8
    active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
