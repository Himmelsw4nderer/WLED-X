from pydantic import BaseModel


class DiscoveredDevice(BaseModel):
    name: str
    ip: str
    mac: str | None = None
    led_count: int = 0
