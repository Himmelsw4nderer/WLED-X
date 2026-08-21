import asyncio

import lumen.console.state as state_module


class _NullManager:
    async def broadcast(self, message: dict) -> None:
        pass


def test_hit_sets_hype_then_decays_over_time(monkeypatch):
    monkeypatch.setattr(state_module, "manager", _NullManager())
    console = state_module.Console()

    clock = [100.0]
    monkeypatch.setattr(state_module.time, "monotonic", lambda: clock[0])

    asyncio.run(console.hit())
    assert console.snapshot().hype == 1.0

    clock[0] += state_module.settings.hype_decay_seconds / 2
    mid_hype = console.snapshot().hype
    assert 0.0 < mid_hype < 1.0

    clock[0] += state_module.settings.hype_decay_seconds
    assert console.snapshot().hype == 0.0


def test_set_merges_param_overrides(monkeypatch):
    monkeypatch.setattr(state_module, "manager", _NullManager())
    console = state_module.Console()

    asyncio.run(console.set({"param_overrides": {"1:speed": 2.0}}))
    asyncio.run(console.set({"param_overrides": {"1:brightness": 0.5}}))

    overrides = console.snapshot().param_overrides
    assert overrides == {"1:speed": 2.0, "1:brightness": 0.5}


def test_set_updates_master_brightness(monkeypatch):
    monkeypatch.setattr(state_module, "manager", _NullManager())
    console = state_module.Console()

    asyncio.run(console.set({"master_brightness": 0.3}))
    assert console.snapshot().master_brightness == 0.3
