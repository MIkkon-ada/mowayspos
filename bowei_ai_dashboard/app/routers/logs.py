from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import crud, models
from ..database import get_db
from ..permissions import get_current_user_name, require_tech_admin

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _row_project_name(row, db: Session) -> str:
    project_id = getattr(row, "project_id", None)
    if project_id is not None:
        return crud.get_project_name_by_id(project_id, db) or getattr(row, "special_project", "") or ""
    return getattr(row, "special_project", "") or ""

_PROTECTED_TYPES = {
    "task": models.Task,
    "issue": models.Issue,
    "achievement": models.Achievement,
}


@router.get("/global")
def global_logs(
    operator: str | None = Query(None),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    date_from: str | None = Query(None),   # YYYY-MM-DD
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    require_tech_admin(current_user, db)

    q = db.query(models.OperationLog)
    if operator:
        q = q.filter(models.OperationLog.operator.contains(operator))
    if action:
        q = q.filter(models.OperationLog.action.contains(action))
    if target_type:
        q = q.filter(models.OperationLog.target_type == target_type)
    if date_from:
        q = q.filter(models.OperationLog.created_at >= date_from)
    if date_to:
        q = q.filter(models.OperationLog.created_at <= date_to + " 23:59:59")

    total = q.count()
    items = (
        q.order_by(models.OperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [crud.to_dict(l) for l in items]}


@router.get("")
def list_logs(target_type: str, target_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    require_tech_admin(current_user, db)

    logs = (
        db.query(models.OperationLog)
        .filter(
            models.OperationLog.target_type == target_type,
            models.OperationLog.target_id == target_id,
        )
        .order_by(models.OperationLog.created_at.asc())
        .all()
    )
    return [crud.to_dict(l) for l in logs]
