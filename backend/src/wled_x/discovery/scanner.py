import asyncio
import ipaddress
import socket

import httpx

from wled_x.discovery.schemas import DiscoveredDevice

PROBE_TIMEOUT = 0.3
CONCURRENCY = 64


def detect_local_cidr() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    return str(ipaddress.ip_network(f"{local_ip}/24", strict=False))


async def scan(cidr: str | None = None, timeout: float = PROBE_TIMEOUT) -> list[DiscoveredDevice]:
    network = ipaddress.ip_network(cidr or detect_local_cidr(), strict=False)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(timeout=timeout) as client:
        results = await asyncio.gather(
            *(_probe_host(client, str(host), semaphore) for host in network.hosts())
        )
    return [device for device in results if device is not None]


async def _probe_host(
    client: httpx.AsyncClient, ip: str, semaphore: asyncio.Semaphore
) -> DiscoveredDevice | None:
    async with semaphore:
        try:
            response = await client.get(f"http://{ip}/json/info")
        except httpx.HTTPError:
            return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if "leds" not in data:
        return None
    leds = data.get("leds", {})
    return DiscoveredDevice(
        name=data.get("name", ip),
        ip=ip,
        mac=data.get("mac"),
        led_count=leds.get("count", 0),
    )
