from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from wled_x.api.schemas import ColorSchemeCreate, ColorSchemeRead, ColorSchemeUpdate
from wled_x.db import get_session
from wled_x.models.color_scheme import ColorScheme

router = APIRouter(prefix="/api/color-schemes", tags=["color-schemes"])


@router.get("", response_model=list[ColorSchemeRead])
def list_color_schemes(session: Session = Depends(get_session)) -> list[ColorScheme]:
    return list(session.exec(select(ColorScheme)).all())


@router.post("", response_model=ColorSchemeRead, status_code=201)
def create_color_scheme(
    payload: ColorSchemeCreate, session: Session = Depends(get_session)
) -> ColorScheme:
    scheme = ColorScheme(name=payload.name, colors=[list(c) for c in payload.colors])
    session.add(scheme)
    session.commit()
    session.refresh(scheme)
    return scheme


@router.patch("/{scheme_id}", response_model=ColorSchemeRead)
def update_color_scheme(
    scheme_id: int, payload: ColorSchemeUpdate, session: Session = Depends(get_session)
) -> ColorScheme:
    scheme = session.get(ColorScheme, scheme_id)
    if scheme is None:
        raise HTTPException(404, "color scheme not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("colors") is not None:
        updates["colors"] = [list(c) for c in updates["colors"]]
    for key, value in updates.items():
        setattr(scheme, key, value)
    session.add(scheme)
    session.commit()
    session.refresh(scheme)
    return scheme


@router.delete("/{scheme_id}", status_code=204)
def delete_color_scheme(scheme_id: int, session: Session = Depends(get_session)) -> None:
    scheme = session.get(ColorScheme, scheme_id)
    if scheme is None:
        raise HTTPException(404, "color scheme not found")
    session.delete(scheme)
    session.commit()
