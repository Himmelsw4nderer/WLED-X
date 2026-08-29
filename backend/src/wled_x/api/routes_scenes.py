from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from wled_x.api.schemas import SceneCreate, SceneRead, SceneUpdate
from wled_x.db import get_session
from wled_x.models.scene import Scene

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneRead])
def list_scenes(session: Session = Depends(get_session)) -> list[Scene]:
    return list(session.exec(select(Scene)).all())


@router.get("/{scene_id}", response_model=SceneRead)
def get_scene(scene_id: int, session: Session = Depends(get_session)) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(404, "scene not found")
    return scene


@router.post("", response_model=SceneRead, status_code=201)
def create_scene(payload: SceneCreate, session: Session = Depends(get_session)) -> Scene:
    scene = Scene(
        name=payload.name,
        assignments=[a.model_dump() for a in payload.assignments],
    )
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return scene


@router.patch("/{scene_id}", response_model=SceneRead)
def update_scene(
    scene_id: int, payload: SceneUpdate, session: Session = Depends(get_session)
) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(404, "scene not found")
    updates = payload.model_dump(exclude_unset=True)
    if "assignments" in updates and updates["assignments"] is not None:
        updates["assignments"] = [dict(a) for a in updates["assignments"]]

    if updates.get("active"):
        others = session.exec(select(Scene).where(Scene.id != scene_id)).all()
        for other in others:
            if other.active:
                other.active = False
                session.add(other)

    for key, value in updates.items():
        setattr(scene, key, value)
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return scene


@router.delete("/{scene_id}", status_code=204)
def delete_scene(scene_id: int, session: Session = Depends(get_session)) -> None:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(404, "scene not found")
    session.delete(scene)
    session.commit()
