from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from lumen.api.schemas import DeviceCreate, DeviceRead, DeviceUpdate
from lumen.db import get_session
from lumen.models.device import Device

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRead])
def list_devices(session: Session = Depends(get_session)) -> list[Device]:
    return list(session.exec(select(Device)).all())


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: int, session: Session = Depends(get_session)) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "device not found")
    return device


@router.post("", response_model=DeviceRead, status_code=201)
def create_device(payload: DeviceCreate, session: Session = Depends(get_session)) -> Device:
    existing = session.exec(select(Device).where(Device.ip == payload.ip)).first()
    if existing is not None:
        raise HTTPException(409, "a device with this ip already exists")
    device = Device(**payload.model_dump())
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: int, payload: DeviceUpdate, session: Session = Depends(get_session)
) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "device not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: int, session: Session = Depends(get_session)) -> None:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "device not found")
    session.delete(device)
    session.commit()
