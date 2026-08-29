from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from wled_x.api.schemas import AudioDeviceOption, AudioSourceRead, AudioSourceUpdate
from wled_x.audio.capture import discover_audio_devices
from wled_x.db import get_session
from wled_x.effects import engine
from wled_x.models.audio_source import AudioSourceConfig

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.get("/devices", response_model=list[AudioDeviceOption])
async def list_audio_devices() -> list[AudioDeviceOption]:
    return await discover_audio_devices()


@router.get("/sources", response_model=list[AudioSourceRead])
def list_audio_sources(session: Session = Depends(get_session)) -> list[AudioSourceConfig]:
    return list(session.exec(select(AudioSourceConfig)).all())


@router.put("/sources/{name}", response_model=AudioSourceRead)
async def update_audio_source(
    name: str, payload: AudioSourceUpdate, session: Session = Depends(get_session)
) -> AudioSourceConfig:
    source = session.get(AudioSourceConfig, name)
    if source is None:
        raise HTTPException(404, "audio source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    session.add(source)
    session.commit()
    session.refresh(source)
    # Swaps the live capture for this slot to match, without restarting the
    # whole render loop -- a no-op if the loop isn't running yet (e.g. tests).
    await engine.reconfigure_audio_sources()
    return source
