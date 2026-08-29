import asyncio
import ipaddress

import httpx
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from wled_x.discovery.schemas import DiscoveredDevice
from wled_x.discovery.wled_client import get_info

SERVICE_TYPE = "_wled._tcp.local."
RESOLVE_TIMEOUT_MS = 1500
HTTP_PROBE_TIMEOUT = 1.5


async def discover(timeout: float = 4.0) -> list[DiscoveredDevice]:
    found_names: set[str] = set()

    def on_state_change(
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        if state_change is ServiceStateChange.Added:
            found_names.add(name)

    infos: list[AsyncServiceInfo] = []
    async with AsyncZeroconf() as aiozc:
        browser = AsyncServiceBrowser(aiozc.zeroconf, SERVICE_TYPE, handlers=[on_state_change])
        await asyncio.sleep(timeout)
        await browser.async_cancel()

        for name in found_names:
            info = AsyncServiceInfo(SERVICE_TYPE, name)
            if await info.async_request(aiozc.zeroconf, RESOLVE_TIMEOUT_MS):
                infos.append(info)

    results = await asyncio.gather(*(_probe(info) for info in infos))
    return [device for device in results if device is not None]


def _first_ipv4(info: AsyncServiceInfo) -> str | None:
    for addr in info.parsed_addresses():
        try:
            if ipaddress.ip_address(addr).version == 4:
                return addr
        except ValueError:
            continue
    return None


async def _probe(info: AsyncServiceInfo) -> DiscoveredDevice | None:
    ip = _first_ipv4(info)
    if ip is None:
        return None
    try:
        data = await get_info(ip, timeout=HTTP_PROBE_TIMEOUT)
    except (httpx.HTTPError, ValueError):
        return None
    leds = data.get("leds", {})
    return DiscoveredDevice(
        name=data.get("name") or info.name.split(".")[0],
        ip=ip,
        mac=data.get("mac"),
        led_count=leds.get("count", 0),
    )
