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

    def set_incoming_handler(self, handler: IncomingHandler) -> None:
        self._incoming_handler = handler

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
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
