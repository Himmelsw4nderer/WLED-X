import numpy as np
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from lumen import db
from lumen.models.device import Device
from lumen.output import device_manager


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture(autouse=True)
def _reset_device_manager_state():
    device_manager._device_cache.clear()
    device_manager._cache_loaded_at = 0.0
    device_manager._pending_online.clear()
    device_manager._last_flush_at = 0.0
    yield
    device_manager._device_cache.clear()
    device_manager._cache_loaded_at = 0.0
    device_manager._pending_online.clear()
    device_manager._last_flush_at = 0.0


async def test_push_frame_sends_and_marks_online(monkeypatch, engine):
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine) as session:
        device = Device(name="d1", ip="10.0.0.5", led_count=2)
        session.add(device)
        session.commit()
        session.refresh(device)
        device_id = device.id

    sent = []
    monkeypatch.setattr(
        device_manager.ddp, "send_frame", lambda ip, pixels: sent.append((ip, pixels))
    )

    pixels = np.zeros((2, 3), dtype=np.uint8)
    await device_manager.push_frame({device_id: pixels})

    assert sent == [("10.0.0.5", pixels)]

    with Session(engine) as session:
        refreshed = session.get(Device, device_id)
        assert refreshed.online is True
        assert refreshed.last_seen is not None


async def test_push_frame_marks_offline_on_send_failure(monkeypatch, engine):
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine) as session:
        device = Device(name="d1", ip="10.0.0.5", led_count=2, online=True)
        session.add(device)
        session.commit()
        session.refresh(device)
        device_id = device.id

    def boom(ip, pixels):
        raise OSError("network unreachable")

    monkeypatch.setattr(device_manager.ddp, "send_frame", boom)

    await device_manager.push_frame({device_id: np.zeros((2, 3), dtype=np.uint8)})

    with Session(engine) as session:
        refreshed = session.get(Device, device_id)
        assert refreshed.online is False


async def test_push_frame_unknown_device_does_not_raise(monkeypatch, engine):
    monkeypatch.setattr(db, "engine", engine)
    await device_manager.push_frame({999: np.zeros((1, 3), dtype=np.uint8)})


async def test_push_frame_caches_device_map_between_calls(monkeypatch, engine):
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine) as session:
        device = Device(name="d1", ip="10.0.0.5", led_count=2)
        session.add(device)
        session.commit()
        session.refresh(device)
        device_id = device.id

    calls = []
    monkeypatch.setattr(device_manager.ddp, "send_frame", lambda ip, pixels: None)

    original_refresh = device_manager._refresh_cache

    def counting_refresh():
        calls.append(1)
        original_refresh()

    monkeypatch.setattr(device_manager, "_refresh_cache", counting_refresh)

    pixels = np.zeros((2, 3), dtype=np.uint8)
    await device_manager.push_frame({device_id: pixels})
    await device_manager.push_frame({device_id: pixels})

    assert len(calls) == 1
