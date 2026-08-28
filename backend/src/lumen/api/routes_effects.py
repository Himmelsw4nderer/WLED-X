import copy
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from lumen.api.schemas import EffectCreate, EffectRead, EffectUpdate
from lumen.db import get_session
from lumen.models.effect import Effect

router = APIRouter(prefix="/api/effects", tags=["effects"])


@router.get("", response_model=list[EffectRead])
def list_effects(session: Session = Depends(get_session)) -> list[Effect]:
    return list(session.exec(select(Effect)).all())


@router.get("/{effect_id}", response_model=EffectRead)
def get_effect(effect_id: int, session: Session = Depends(get_session)) -> Effect:
    effect = session.get(Effect, effect_id)
    if effect is None:
        raise HTTPException(404, "effect not found")
    return effect


@router.post("", response_model=EffectRead, status_code=201)
def create_effect(payload: EffectCreate, session: Session = Depends(get_session)) -> Effect:
    effect = Effect(
        name=payload.name,
        description=payload.description,
        graph=payload.graph,
        exposed_params=[p.model_dump() for p in payload.exposed_params],
    )
    session.add(effect)
    session.commit()
    session.refresh(effect)
    return effect


@router.post("/{effect_id}/duplicate", response_model=EffectRead, status_code=201)
def duplicate_effect(effect_id: int, session: Session = Depends(get_session)) -> Effect:
    source = session.get(Effect, effect_id)
    if source is None:
        raise HTTPException(404, "effect not found")
    existing_names = set(session.exec(select(Effect.name)).all())
    name = f"{source.name} (copy)"
    n = 2
    while name in existing_names:
        name = f"{source.name} (copy {n})"
        n += 1
    effect = Effect(
        name=name,
        description=source.description,
        graph=copy.deepcopy(source.graph),
        exposed_params=[dict(p) for p in source.exposed_params],
    )
    session.add(effect)
    session.commit()
    session.refresh(effect)
    return effect


@router.patch("/{effect_id}", response_model=EffectRead)
def update_effect(
    effect_id: int, payload: EffectUpdate, session: Session = Depends(get_session)
) -> Effect:
    effect = session.get(Effect, effect_id)
    if effect is None:
        raise HTTPException(404, "effect not found")
    updates = payload.model_dump(exclude_unset=True)
    if "exposed_params" in updates and updates["exposed_params"] is not None:
        updates["exposed_params"] = [dict(p) for p in updates["exposed_params"]]
    for key, value in updates.items():
        setattr(effect, key, value)
    effect.updated_at = datetime.now(UTC)
    session.add(effect)
    session.commit()
    session.refresh(effect)
    return effect


@router.delete("/{effect_id}", status_code=204)
def delete_effect(effect_id: int, session: Session = Depends(get_session)) -> None:
    effect = session.get(Effect, effect_id)
    if effect is None:
        raise HTTPException(404, "effect not found")
    session.delete(effect)
    session.commit()
