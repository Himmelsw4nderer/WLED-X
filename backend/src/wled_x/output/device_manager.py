"""Interface contract between the render loop (wled_x.effects.engine) and the
physical device output (wled_x.output.ddp + wled_x.discovery).

The render loop calls `push_frame` once per rendered frame with one uint8
(N, 3) RGB array per device id; this module is responsible for turning that
into DDP UDP packets addressed to each device's IP and tracking online state.
"""

import time
from datetime import UTC, datetime

import numpy as np
from sqlmodel import Session, select

from wled_x import db
from wled_x.models.device import Device
from wled_x.output import ddp

CACHE_TTL_SECONDS = 5.0
ONLINE_STATE_FLUSH_SECONDS = 2.0

_device_cache: dict[int, tuple[str, int]] = {}
_cache_loaded_at = 0.0
_pending_online: dict[int, bool] = {}
_last_flush_at = 0.0


def _refresh_cache() -> None:
    global _cache_loaded_at
    with Session(db.engine) as session:
        devices = session.exec(select(Device)).all()
    _device_cache.clear()
    _device_cache.update({d.id: (d.ip, d.led_count) for d in devices if d.id is not None})
    _cache_loaded_at = time.monotonic()


def _flush_online_state() -> None:
    global _last_flush_at
    if _pending_online:
        with Session(db.engine) as session:
            for device_id, online in _pending_online.items():
                device = session.get(Device, device_id)
                if device is None:
                    continue
                device.online = online
                if online:
                    device.last_seen = datetime.now(UTC)
                session.add(device)
            session.commit()
        _pending_online.clear()
    _last_flush_at = time.monotonic()


async def push_frame(pixel_buffers: dict[int, np.ndarray]) -> None:
    """pixel_buffers: device_id -> (N, 3) uint8 RGB array, one row per LED."""
    now = time.monotonic()
    # This runs every render frame (~60Hz). Hitting sqlite for a fresh device list
    # or writing online/last_seen on every call would add DB latency to the hot
    # path for no real benefit, so the ip/led_count map is cached and online-state
    # writes are batched and flushed at most every couple of seconds.
    if now - _cache_loaded_at > CACHE_TTL_SECONDS:
        _refresh_cache()

    for device_id, pixels in pixel_buffers.items():
        target = _device_cache.get(device_id)
        if target is None:
            _pending_online[device_id] = False
            continue
        ip, _led_count = target
        try:
            ddp.send_frame(ip, pixels)
        except OSError:
            _pending_online[device_id] = False
        else:
            _pending_online[device_id] = True

    if now - _last_flush_at > ONLINE_STATE_FLUSH_SECONDS:
        _flush_online_state()
