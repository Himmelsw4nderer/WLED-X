from typing import Any

import httpx

DEFAULT_TIMEOUT = 1.5


async def get_info(ip: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{ip}/json/info")
        response.raise_for_status()
        return response.json()


async def get_state(ip: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{ip}/json/state")
        response.raise_for_status()
        return response.json()


async def set_state(ip: str, timeout: float = DEFAULT_TIMEOUT, **kwargs: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"http://{ip}/json/state", json=kwargs)
        response.raise_for_status()
        return response.json()
