from fastapi import APIRouter
from pydantic import BaseModel

from lumen.discovery import mdns, scanner
from lumen.discovery.schemas import DiscoveredDevice

router = APIRouter(prefix="/api/devices", tags=["discovery"])


class ScanRequest(BaseModel):
    cidr: str | None = None


@router.get("/discover/mdns", response_model=list[DiscoveredDevice])
async def discover_mdns() -> list[DiscoveredDevice]:
    return await mdns.discover()


@router.post("/discover/scan", response_model=list[DiscoveredDevice])
async def discover_scan(payload: ScanRequest = ScanRequest()) -> list[DiscoveredDevice]:
    return await scanner.scan(cidr=payload.cidr)
