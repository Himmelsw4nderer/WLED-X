"""In-memory live console state: master brightness, active scene, per-param
overrides, and a decaying "hype" pulse for pre-drop buildups. A single
process-wide singleton; the render loop reads it, the WS hub's inbound
messages write to it.

`param_overrides` keys use the convention `"{effect_id}:{node_id}:{param_key}"`
-- effect_id so the same effect used in two different scene assignments can
still be overridden independently, and node_id so two instances of the same
node type in one graph (e.g. two Constant nodes both exposing "value") don't
collide onto the same override and become impossible to control separately.
"""

import time
from typing import Any

from wled_x.api.schemas import ConsoleState
from wled_x.api.ws import manager
from wled_x.config import settings


class Console:
    def __init__(self) -> None:
        self._state = ConsoleState()
        self._hit_at: float | None = None

    def _decayed_hype(self) -> float:
        if self._hit_at is None:
            return self._state.hype
        elapsed = time.monotonic() - self._hit_at
        remaining = 1.0 - elapsed / settings.hype_decay_seconds
        return max(remaining, 0.0)

    def snapshot(self) -> ConsoleState:
        state = self._state.model_copy()
        state.hype = self._decayed_hype()
        return state

    async def set(self, partial: dict[str, Any]) -> None:
        for key, value in partial.items():
            if key == "param_overrides" and isinstance(value, dict):
                self._state.param_overrides = {**self._state.param_overrides, **value}
            elif hasattr(self._state, key):
                setattr(self._state, key, value)
        await self._broadcast()

    async def clear_param_overrides(self) -> None:
        """Drop every live fader-bank override. The render loop calls this the
        moment the active scene changes so one scene's rides can't bleed onto
        the next -- each scene's values live on its own row (Scene.assignments
        [].params) and the fader bank reseeds from there."""
        if not self._state.param_overrides:
            return
        self._state.param_overrides = {}
        await self._broadcast()

    async def hit(self) -> None:
        self._hit_at = time.monotonic()
        self._state.hype = 1.0
        await self._broadcast()

    async def _broadcast(self) -> None:
        await manager.broadcast({"type": "console_state", **self.snapshot().model_dump()})


console = Console()


async def _handle_message(message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if message_type == "console_set":
        await console.set({key: value for key, value in message.items() if key != "type"})
    elif message_type == "console_hit":
        await console.hit()


manager.set_incoming_handler(_handle_message)
