from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine, select

from wled_x.config import settings
from wled_x.models.audio_source import AudioSourceConfig
from wled_x.models.playlist import Playlist  # noqa: F401  -- register the table

engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # create_all only creates missing tables, not missing columns on tables that
    # already exist -- there's no Alembic here yet, so new columns on existing
    # models need a one-line entry here to reach databases created before them.
    _add_column_if_missing("fixture", "reverse", "BOOLEAN NOT NULL DEFAULT 0")
    _ensure_audio_source_defaults()


def _ensure_audio_source_defaults() -> None:
    # Seeded once from the env-configured defaults (see config.py); the DB
    # row is the source of truth after that -- the audio device picker in
    # the console UI edits these rows, not the environment.
    with Session(engine) as session:
        existing = set(session.exec(select(AudioSourceConfig.name)).all())
        defaults = [
            AudioSourceConfig(
                name="desktop", enabled=True, mode="loopback", device=settings.audio_device
            ),
            AudioSourceConfig(
                name="mic",
                enabled=settings.audio_mic_enabled,
                mode="input",
                device=settings.audio_mic_device,
            ),
        ]
        for row in defaults:
            if row.name not in existing:
                session.add(row)
        session.commit()


def _add_column_if_missing(table: str, column: str, ddl_type_and_default: str) -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type_and_default}")


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session
