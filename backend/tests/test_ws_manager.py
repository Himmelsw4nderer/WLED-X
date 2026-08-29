import asyncio

from wled_x.api.ws import ConnectionManager


class _FakeSocket:
    """Stands in for a WebSocket connection whose `send_json` can be held
    open on demand, to simulate a slow-draining client without a real
    network socket."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.gate: asyncio.Event | None = None

    async def send_json(self, message: dict) -> None:
        if self.gate is not None:
            await self.gate.wait()
        self.sent.append(message)


async def test_broadcast_latest_does_not_await_the_send():
    # The whole point: this must be a plain sync call the render loop can
    # fire off without yielding control, so a slow client can never stall it.
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    manager._connections.add(ws)

    manager.broadcast_latest({"n": 1})
    # Nothing has actually been sent yet -- the send only runs once we give
    # the event loop a chance to run the task broadcast_latest scheduled.
    assert ws.sent == []

    await asyncio.sleep(0)
    assert ws.sent == [{"n": 1}]


async def test_broadcast_latest_drops_messages_while_a_send_is_still_in_flight():
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    ws.gate = asyncio.Event()
    manager._connections.add(ws)

    manager.broadcast_latest({"n": 1})
    await asyncio.sleep(0)  # let the first send start and block on the gate

    # These land while {"n": 1}'s send hasn't completed -- for a live preview
    # only the newest snapshot matters, so they should be dropped rather than
    # queued up behind the slow connection.
    manager.broadcast_latest({"n": 2})
    manager.broadcast_latest({"n": 3})
    await asyncio.sleep(0)

    ws.gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert ws.sent == [{"n": 1}]


async def test_broadcast_latest_sends_again_once_the_previous_send_completes():
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    manager._connections.add(ws)

    manager.broadcast_latest({"n": 1})
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    manager.broadcast_latest({"n": 2})
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert ws.sent == [{"n": 1}, {"n": 2}]


async def test_broadcast_latest_drops_the_connection_on_send_failure():
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()

    class _BrokenSocket(_FakeSocket):
        async def send_json(self, message: dict) -> None:
            raise ConnectionResetError

    ws = _BrokenSocket()
    manager._connections.add(ws)

    manager.broadcast_latest({"n": 1})
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert ws not in manager._connections
    assert (ws, "") not in manager._inflight


async def test_disconnect_clears_any_inflight_task():
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    ws.gate = asyncio.Event()
    manager._connections.add(ws)

    manager.broadcast_latest({"n": 1})
    await asyncio.sleep(0)
    assert (ws, "") in manager._inflight

    await manager.disconnect(ws)
    assert ws not in manager._connections
    assert (ws, "") not in manager._inflight


async def test_broadcast_latest_partitions_inflight_by_message_type():
    # A busy high-frequency type (e.g. "frame") must never block a different,
    # much rarer type (e.g. "playlist") sharing the same connection -- they
    # used to share one in-flight slot per connection, which silently starved
    # the rare type out almost every time.
    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    ws.gate = asyncio.Event()
    manager._connections.add(ws)

    manager.broadcast_latest({"type": "frame", "n": 1})
    await asyncio.sleep(0)  # "frame" send is now in flight, blocked on the gate

    # "playlist" gets its own in-flight slot, so it isn't dropped just
    # because "frame" is still pending on this same connection -- both sends
    # share the fake socket's single gate, so open it to let both through.
    manager.broadcast_latest({"type": "playlist", "n": 2})
    ws.gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert {"type": "frame", "n": 1} in ws.sent
    assert {"type": "playlist", "n": 2} in ws.sent


async def test_broadcast_latest_is_safe_to_call_off_the_event_loop_thread():
    # Manual playlist next/prev comes in through a plain `def` FastAPI route,
    # which runs in a worker thread with no running event loop.
    import concurrent.futures

    manager = ConnectionManager()
    manager._loop = asyncio.get_running_loop()
    ws = _FakeSocket()
    manager._connections.add(ws)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        await asyncio.get_running_loop().run_in_executor(
            pool, manager.broadcast_latest, {"n": 1}
        )

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert ws.sent == [{"n": 1}]
