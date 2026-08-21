import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from lumen import db
from lumen.main import create_app


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s, engine


@pytest.fixture
def client(session, monkeypatch):
    s, engine = session
    monkeypatch.setattr(db, "engine", engine)

    def override_get_session():
        yield s

    app = create_app()
    app.dependency_overrides[db.get_session] = override_get_session
    with TestClient(app) as c:
        yield c
