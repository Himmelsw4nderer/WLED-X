from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from wled_x.api.schemas import FixtureCreate, FixtureRead, FixtureUpdate
from wled_x.db import get_session
from wled_x.models.fixture import Fixture

router = APIRouter(prefix="/api/fixtures", tags=["fixtures"])


@router.get("", response_model=list[FixtureRead])
def list_fixtures(session: Session = Depends(get_session)) -> list[Fixture]:
    return list(session.exec(select(Fixture)).all())


@router.get("/{fixture_id}", response_model=FixtureRead)
def get_fixture(fixture_id: int, session: Session = Depends(get_session)) -> Fixture:
    fixture = session.get(Fixture, fixture_id)
    if fixture is None:
        raise HTTPException(404, "fixture not found")
    return fixture


@router.post("", response_model=FixtureRead, status_code=201)
def create_fixture(payload: FixtureCreate, session: Session = Depends(get_session)) -> Fixture:
    if len(payload.points) < 2:
        raise HTTPException(422, "a fixture needs at least 2 points to define its path")
    fixture = Fixture(**payload.model_dump())
    session.add(fixture)
    session.commit()
    session.refresh(fixture)
    return fixture


@router.patch("/{fixture_id}", response_model=FixtureRead)
def update_fixture(
    fixture_id: int, payload: FixtureUpdate, session: Session = Depends(get_session)
) -> Fixture:
    fixture = session.get(Fixture, fixture_id)
    if fixture is None:
        raise HTTPException(404, "fixture not found")
    updates = payload.model_dump(exclude_unset=True)
    if "points" in updates and updates["points"] is not None and len(updates["points"]) < 2:
        raise HTTPException(422, "a fixture needs at least 2 points to define its path")
    for key, value in updates.items():
        setattr(fixture, key, value)
    session.add(fixture)
    session.commit()
    session.refresh(fixture)
    return fixture


@router.delete("/{fixture_id}", status_code=204)
def delete_fixture(fixture_id: int, session: Session = Depends(get_session)) -> None:
    fixture = session.get(Fixture, fixture_id)
    if fixture is None:
        raise HTTPException(404, "fixture not found")
    session.delete(fixture)
    session.commit()
