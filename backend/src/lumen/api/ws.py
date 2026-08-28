"""Shared WebSocket hub for /ws/live.

Broadcasts JSON messages to every connected browser (frame previews, console
state pushes) and forwards inbound client messages to a single registered
handler. Modules that need to react to client messages (console overrides,
scene switches, ...) call `set_incoming_handler` once at startup instead of
each owning their own socket.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

IncomingHandler = Callable[[dict[str, Any]], Awaitable[None]]


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._incoming_handler: IncomingHandler | None = None
        # One in-flight send per connection, used only by broadcast_latest --
        # see there for why.
        self._inflight: dict[WebSocket, asyncio.Task[None]] = {}

    def set_incoming_handler(self, handler: IncomingHandler) -> None:
        self._incoming_handler = handler

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        self._inflight.pop(ws, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Reliable, ordered broadcast: awaits every connection's send
        before returning. Fine for low-frequency, must-not-drop messages
        like console state. Do NOT call this from the render loop's tick --
        a client that drains its socket slowly (a backgrounded/throttled
        browser tab, a laggy network) would stall this coroutine, and since
        the render loop awaits its broadcasts inline that would throttle
        the entire loop, including real device output, down to whatever
        rate the slowest browser tab can keep up with. That's exactly what
        `broadcast_latest` exists to avoid."""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    def broadcast_latest(self, message: dict[str, Any]) -> None:
        """Fire-and-forget broadcast for high-frequency "latest value wins"
        streams -- the render loop's per-tick frame/audio previews. Returns
        immediately without waiting on any client's socket, so a slow or
        stuck browser tab can never throttle the caller (the render loop,
        which also drives real device output via DDP). If a connection
        hasn't finished draining the *previous* message yet, this one is
        simply dropped for that connection rather than queued -- for a live
        preview only the newest snapshot matters, and queuing behind a
        permanently slow client would just leak memory forever."""
        for ws in list(self._connections):
            task = self._inflight.get(ws)
            if task is not None and not task.done():
                continue
            self._inflight[ws] = asyncio.create_task(self._send_one(ws, message))

    async def _send_one(self, ws: WebSocket, message: dict[str, Any]) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            async with self._lock:
                self._connections.discard(ws)
        finally:
            self._inflight.pop(ws, None)

    async def handle_message(self, message: dict[str, Any]) -> None:
        if self._incoming_handler is not None:
            await self._incoming_handler(message)
        else:
            logger.debug("no incoming WS handler registered, dropping message: %s", message)


manager = ConnectionManager()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await manager.handle_message(message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
