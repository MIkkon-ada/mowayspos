from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import source_type as ST
from ..permissions import (
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_owner_or_admin,
)
from ..services.notify import person_id_for_name as _pid_for_name
from ..services.project_resolution import resolve_project_context
from ..services.project_close import require_project_business_writable

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _row_project_id_for_read(row: models.Achievement, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]


def _row_project_name(row: models.Achievement, db: Session) -> str:
    resolved = resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )
    return resolved["project_name"] or row.special_project or ""


# ── 端点 ──────────────────────────────────────────────────────


@router.get("")
def list_achievements(
    project_id: int | None = None,
    achievement_type: str | None = None,
    special_project: str | None = None,
    owner: str | None = None,
    reuse_tag: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)

    resolution = resolve_project_context(
        db,
        project_id=project_id,
        special_project=special_project,
    )
    effective_project_id: int | None = resolution["project_id"]
    if project_id is not None and not resolution["is_valid"]:
        raise HTTPException(404, "project not found")
    if project_id is None and special_project and effective_project_id is None:
        return []

    if effective_project_id is not None:
        require_project_access(current_user, effective_project_id, db)
    elif not special_project:
        _require_global_read_scope(context)

    q = db.query(models.Achievement)
    if effective_project_id is not None:
        q = q.filter(models.Achievement.project_id == effective_project_id)

    if achievement_type:
        q = q.filter(models.Achievement.achievement_type == achievement_type)
    if owner:
        q = q.filter(models.Achievement.owner == owner)
    if reuse_tag:
        q = q.filter(models.Achievement.reuse_tag.like(f"%{reuse_tag}%"))
    return [crud.to_dict(r) for r in q.order_by(models.Achievement.updated_at.desc()).all()]


@router.post("")
def create_achievement(
    payload: schemas.AchievementPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    project_id = payload.project_id
    if project_id is None:
        raise HTTPException(422, "project_id is required")

    require_project_owner_or_admin(current_user, project_id, db)
    require_project_business_writable(project_id, db)

    crud.validate_subtask_link(db, project_id, payload.related_task_id, payload.related_subtask_id)

    data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    row = models.Achievement(**data)
    row.source_type = ST.normalize(payload.source_type or "人工录入")
    row.project_id = project_id
    row.owner_id = _pid_for_name(row.owner or "", db)
    if not row.special_project:
        row.special_project = resolve_project_context(
            db,
            project_id=project_id,
            special_project=payload.special_project,
        )["project_name"] or payload.special_project or ""
    db.add(row)
    db.flush()
    crud.log(db, current_user, "achievement_create", "achievement", row.id, {}, crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


@router.get("/{row_id}")
def get_achievement(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Achievement, row_id)
    if not row:
        raise HTTPException(404, "achievement not found")
    project_id = _row_project_id_for_read(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return crud.to_dict(row)


@router.put("/{row_id}")
def update_achievement(
    row_id: int,
    payload: schemas.AchievementPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Achievement, row_id)
    if not row:
        raise HTTPException(404, "achievement not found")

    project_id = row.project_id
    if project_id is None:
        if not context.get("is_tech_admin"):
            raise HTTPException(403, "permission denied")
    else:
        require_project_owner_or_admin(current_user, project_id, db)

    require_project_business_writable(project_id, db)

    crud.validate_subtask_link(db, project_id, payload.related_task_id if payload.related_task_id is not None else row.related_task_id, payload.related_subtask_id)

    before = crud.to_dict(row)
    update_data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    if "source_type" in update_data:
        update_data["source_type"] = ST.normalize(update_data["source_type"] or "人工录入")
    crud.update_model(row, update_data)
    row.owner_id = _pid_for_name(row.owner or "", db)

    if payload.project_id is not None:
        row.project_id = payload.project_id
    if not row.special_project:
        row.special_project = resolve_project_context(
            db,
            project_id=row.project_id or project_id,
            special_project=payload.special_project,
        )["project_name"] or payload.special_project or ""

    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "achievement_update", "achievement", row.id, before, payload.model_dump(), project_id=row.project_id or project_id)
    db.commit()
    return crud.to_dict(row)


@router.delete("/{row_id}")
def delete_achievement(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Achievement, row_id)
    if not row:
        raise HTTPException(404, "achievement not found")

    project_id = row.project_id
    if project_id is None:
        if not context.get("is_tech_admin"):
            raise HTTPException(403, "permission denied")
    else:
        require_project_owner_or_admin(current_user, project_id, db)

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    crud.log(db, current_user, "achievement_delete", "achievement", row_id, before, {})
    db.delete(row)
    db.commit()
    return {"ok": True}
