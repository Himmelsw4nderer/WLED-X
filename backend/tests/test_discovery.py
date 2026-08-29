import ipaddress

import httpx

from wled_x.discovery import mdns, scanner
from wled_x.discovery.schemas import DiscoveredDevice


class _FakeServiceInfo:
    def __init__(self, name: str, addresses: list[str]) -> None:
        self.name = name
        self._addresses = addresses

    def parsed_addresses(self) -> list[str]:
        return self._addresses


def test_first_ipv4_picks_v4_over_v6():
    info = _FakeServiceInfo("wled-1._wled._tcp.local.", ["fe80::1", "10.0.0.5"])
    assert mdns._first_ipv4(info) == "10.0.0.5"


def test_first_ipv4_none_when_no_addresses():
    info = _FakeServiceInfo("wled-1._wled._tcp.local.", [])
    assert mdns._first_ipv4(info) is None


async def test_probe_builds_discovered_device(monkeypatch):
    info = _FakeServiceInfo("wled-livingroom._wled._tcp.local.", ["10.0.0.7"])

    async def fake_get_info(ip: str, timeout: float = 1.5):
        assert ip == "10.0.0.7"
        return {"name": "Living Room", "mac": "aa:bb:cc", "leds": {"count": 144}}

    monkeypatch.setattr(mdns, "get_info", fake_get_info)

    device = await mdns._probe(info)

    assert device == DiscoveredDevice(
        name="Living Room", ip="10.0.0.7", mac="aa:bb:cc", led_count=144
    )


async def test_probe_returns_none_on_http_error(monkeypatch):
    info = _FakeServiceInfo("wled-x._wled._tcp.local.", ["10.0.0.9"])

    async def fake_get_info(ip: str, timeout: float = 1.5):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(mdns, "get_info", fake_get_info)

    assert await mdns._probe(info) is None


async def test_discover_end_to_end(monkeypatch):
    found = _FakeServiceInfo("wled-a._wled._tcp.local.", ["10.0.0.10"])

    class FakeBrowser:
        def __init__(self, zc, service_type, handlers):
            for handler in handlers:
                handler(zc, service_type, found.name, mdns.ServiceStateChange.Added)

        async def async_cancel(self):
            pass

    class FakeServiceInfo:
        def __init__(self, service_type, name):
            self.service_type = service_type
            self.name = name

        async def async_request(self, zc, timeout_ms):
            return True

        def parsed_addresses(self):
            return found._addresses

    class FakeAsyncZeroconf:
        def __init__(self):
            self.zeroconf = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def fake_get_info(ip: str, timeout: float = 1.5):
        return {"name": "A", "mac": "mac-a", "leds": {"count": 10}}

    monkeypatch.setattr(mdns, "AsyncZeroconf", FakeAsyncZeroconf)
    monkeypatch.setattr(mdns, "AsyncServiceBrowser", FakeBrowser)
    monkeypatch.setattr(mdns, "AsyncServiceInfo", FakeServiceInfo)
    monkeypatch.setattr(mdns, "get_info", fake_get_info)

    devices = await mdns.discover(timeout=0.01)

    assert devices == [DiscoveredDevice(name="A", ip="10.0.0.10", mac="mac-a", led_count=10)]


class _FakeUDPSocket:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self, addr):
        pass

    def getsockname(self):
        return ("192.168.50.42", 12345)


def test_detect_local_cidr(monkeypatch):
    monkeypatch.setattr(scanner.socket, "socket", lambda *a, **kw: _FakeUDPSocket())
    assert scanner.detect_local_cidr() == "192.168.50.0/24"


def _mock_handler(responses: dict[str, dict]):
    async def handler(request: httpx.Request) -> httpx.Response:
        ip = request.url.host
        if ip in responses:
            return httpx.Response(200, json=responses[ip])
        return httpx.Response(404)

    return handler


async def test_scan_finds_wled_devices_only(monkeypatch):
    cidr = "203.0.113.0/30"
    hosts = list(ipaddress.ip_network(cidr).hosts())
    wled_ip = str(hosts[0])
    plain_http_ip = str(hosts[1])

    responses = {wled_ip: {"name": "Strip", "mac": "aabbccddeeff", "leds": {"count": 30}}}
    transport = httpx.MockTransport(_mock_handler(responses))
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(scanner.httpx, "AsyncClient", fake_async_client)

    devices = await scanner.scan(cidr=cidr)

    assert devices == [DiscoveredDevice(name="Strip", ip=wled_ip, mac="aabbccddeeff", led_count=30)]
    assert plain_http_ip not in [d.ip for d in devices]


async def test_scan_ignores_non_wled_json_response(monkeypatch):
    cidr = "203.0.113.4/30"
    hosts = list(ipaddress.ip_network(cidr).hosts())
    non_wled_ip = str(hosts[0])

    responses = {non_wled_ip: {"hello": "world"}}
    transport = httpx.MockTransport(_mock_handler(responses))
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(scanner.httpx, "AsyncClient", fake_async_client)

    devices = await scanner.scan(cidr=cidr)

    assert devices == []
