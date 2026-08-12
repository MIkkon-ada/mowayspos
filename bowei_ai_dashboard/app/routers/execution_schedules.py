from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import get_current_user_name, get_user_context_from_db, get_all_project_roles
from ..services.project_close import require_project_business_writable
from ..services.notify import person_id_for_name
from ..time_utils import utc_now

router = APIRouter(tags=["execution-schedules"])
FINAL_STATUSES = {"已完成", "已取消"}


def to_schedule_dict(row: models.ExecutionSchedule, *, today: date | None = None) -> dict:
    today = today or utc_now().date()
    result = crud.to_dict(row)
    result["is_overdue"] = bool(not row.is_deleted and row.status not in FINAL_STATUSES and row.due_date < today)
    result["is_due_soon"] = bool(not result["is_overdue"] and row.status not in FINAL_STATUSES and row.due_date == today + timedelta(days=1))
    return result


def _parent(row: models.ExecutionSchedule, db: Session):
    subtask = db.get(models.SubTask, row.subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not subtask or not task or subtask.is_deleted or task.is_deleted:
        raise HTTPException(404, "关键任务不存在")
    return subtask, task


def _can_write(current_user: str, context: dict, subtask: models.SubTask, task: models.Task, db: Session) -> bool:
    if context.get("is_tech_admin"):
        return True
    if (context.get("name") or "") == (subtask.assignee or ""):
        return True
    pid = context.get("person_id")
    return bool(pid and task.project_id and set(get_all_project_roles(pid, task.project_id, db)) & {"owner", "coordinator"})


def _require_write(current_user: str, context: dict, subtask: models.SubTask, task: models.Task, db: Session) -> None:
    if not task.project_id:
        raise HTTPException(403, "permission denied")
    require_project_business_writable(task.project_id, db)
    if not _can_write(current_user, context, subtask, task, db):
        raise HTTPException(403, "permission denied")


@router.get("/api/subtasks/{subtask_id}/execution-schedules")
def list_execution_schedules(subtask_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    subtask = db.get(models.SubTask, subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not subtask or not task:
        raise HTTPException(404, "关键任务不存在")
    rows = db.query(models.ExecutionSchedule).filter_by(subtask_id=subtask_id, is_deleted=False).order_by(models.ExecutionSchedule.start_date, models.ExecutionSchedule.due_date, models.ExecutionSchedule.id).all()
    return [to_schedule_dict(row) for row in rows]


@router.post("/api/subtasks/{subtask_id}/execution-schedules")
def create_execution_schedule(subtask_id: int, payload: schemas.ExecutionSchedulePayload, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    subtask = db.get(models.SubTask, subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not subtask or not task:
        raise HTTPException(404, "关键任务不存在")
    _require_write(current_user, context, subtask, task, db)
    data = payload.model_dump()
    if data["assignee_id"]:
        person = db.get(models.Person, data["assignee_id"])
        if not person:
            raise HTTPException(422, "负责人不存在")
        data["assignee"] = person.name
    elif data["assignee"]:
        data["assignee_id"] = person_id_for_name(data["assignee"], db)
    row = models.ExecutionSchedule(subtask_id=subtask_id, created_by=current_user, updated_by=current_user, **data)
    db.add(row); db.flush()
    crud.log(db, current_user, "execution_schedule_create", "execution_schedule", row.id, {}, crud.to_dict(row), project_id=task.project_id)
    db.commit(); db.refresh(row)
    return to_schedule_dict(row)


@router.patch("/api/execution-schedules/{schedule_id}")
def update_execution_schedule(schedule_id: int, payload: schemas.ExecutionSchedulePayload, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, schedule_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "执行安排不存在")
    subtask, task = _parent(row, db); _require_write(current_user, context, subtask, task, db)
    before = crud.to_dict(row); crud.update_model(row, payload.model_dump()); row.updated_by = current_user
    crud.log(db, current_user, "execution_schedule_update", "execution_schedule", row.id, before, crud.to_dict(row), project_id=task.project_id)
    db.commit(); db.refresh(row)
    return to_schedule_dict(row)


@router.delete("/api/execution-schedules/{schedule_id}")
def delete_execution_schedule(schedule_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, schedule_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "执行安排不存在")
    subtask, task = _parent(row, db); _require_write(current_user, context, subtask, task, db)
    row.is_deleted = True; row.updated_by = current_user
    crud.log(db, current_user, "execution_schedule_delete", "execution_schedule", row.id, {}, {"is_deleted": True}, project_id=task.project_id)
    db.commit()
    return {"ok": True}
