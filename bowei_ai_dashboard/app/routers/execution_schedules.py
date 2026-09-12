from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import get_current_user_name, get_user_context_from_db, get_all_project_roles
from ..services.project_close import require_project_business_writable
from ..services.key_task_execution import record_execution_event
from ..services.notify import person_id_for_name
from ..time_utils import utc_now

router = APIRouter(tags=["execution-schedules"])
FINAL_STATUSES = {"已完成", "已取消"}


def to_schedule_dict(row: models.ExecutionSchedule, *, today: date | None = None) -> dict:
    today = today or utc_now().date()
    result = crud.to_dict(row)
    result["is_overdue"] = bool(
        not row.is_deleted
        and row.status not in FINAL_STATUSES
        and (row.due_kind == "exact" or (not row.due_kind and row.due_date is not None))
        and row.due_date
        and row.due_date < today
    )
    result["is_due_soon"] = bool(
        not result["is_overdue"]
        and row.status not in FINAL_STATUSES
        and (row.due_kind == "exact" or (not row.due_kind and row.due_date is not None))
        and row.due_date
        and row.due_date == today + timedelta(days=1)
    )
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


def _validate_people(task: models.Task, payload: schemas.ExecutionSchedulePayload, db: Session) -> dict[int, models.Person]:
    requested_ids = set(payload.collaborator_ids or [])
    if payload.assignee_id:
        requested_ids.add(payload.assignee_id)
    if requested_ids:
        member_ids = {
            value
            for (value,) in db.query(models.ProjectMember.person_id)
            .filter(models.ProjectMember.project_id == task.project_id)
            .all()
        }
        if not requested_ids.issubset(member_ids):
            raise HTTPException(422, "负责人或协同人不属于该项目")
    people = {
        person.id: person
        for person in db.query(models.Person).filter(models.Person.id.in_(requested_ids)).all()
    } if requested_ids else {}
    if requested_ids - set(people):
        raise HTTPException(422, "负责人或协同人不存在")
    return people


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
    if subtask.status == "已完成":
        raise HTTPException(409, "已完成的关键任务必须先重新打开，才能新增任务计划")
    data = payload.model_dump()
    people = _validate_people(task, payload, db)
    if data["assignee_id"]:
        data["assignee"] = people[data["assignee_id"]].name
    elif data["assignee"]:
        data["assignee_id"] = person_id_for_name(data["assignee"], db)
    row = models.ExecutionSchedule(subtask_id=subtask_id, created_by=current_user, updated_by=current_user, **data)
    db.add(row); db.flush()
    log_row = crud.log(db, current_user, "execution_schedule_create", "execution_schedule", row.id, {}, crud.to_dict(row), project_id=task.project_id)
    db.flush()
    now = utc_now()
    record_execution_event(
        db,
        project_id=task.project_id,
        key_task_id=subtask.id,
        execution_plan_id=row.id,
        event_type="execution_plan_created",
        source_type="execution_schedule",
        source_id=row.id,
        dedupe_key=f"operation_log:{log_row.id}:execution-plan-create",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=False,
        status_after=row.status,
        progress_summary=f"新增任务计划：{row.title}",
    )
    db.commit(); db.refresh(row)
    return to_schedule_dict(row)


@router.patch("/api/execution-schedules/{schedule_id}")
def update_execution_schedule(schedule_id: int, payload: schemas.ExecutionSchedulePayload, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, schedule_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "执行安排不存在")
    subtask, task = _parent(row, db); _require_write(current_user, context, subtask, task, db)
    people = _validate_people(task, payload, db)
    before = crud.to_dict(row); crud.update_model(row, payload.model_dump()); row.updated_by = current_user
    if payload.assignee_id:
        row.assignee = people[payload.assignee_id].name
    log_row = crud.log(db, current_user, "execution_schedule_update", "execution_schedule", row.id, before, crud.to_dict(row), project_id=task.project_id)
    db.flush()
    now = utc_now()
    record_execution_event(
        db,
        project_id=task.project_id,
        key_task_id=subtask.id,
        execution_plan_id=row.id,
        event_type="execution_plan_status_changed" if before.get("status") != row.status else "execution_plan_changed",
        source_type="execution_schedule",
        source_id=row.id,
        dedupe_key=f"operation_log:{log_row.id}:execution-plan-update",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=False,
        status_before=before.get("status"),
        status_after=row.status,
        progress_summary=f"任务计划已更新：{row.title}",
    )
    db.commit(); db.refresh(row)
    return to_schedule_dict(row)


@router.delete("/api/execution-schedules/{schedule_id}")
def delete_execution_schedule(schedule_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, schedule_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "执行安排不存在")
    subtask, task = _parent(row, db); _require_write(current_user, context, subtask, task, db)
    before = crud.to_dict(row)
    row.is_deleted = True; row.updated_by = current_user
    log_row = crud.log(db, current_user, "execution_schedule_delete", "execution_schedule", row.id, before, {"is_deleted": True}, project_id=task.project_id)
    db.flush()
    now = utc_now()
    record_execution_event(
        db,
        project_id=task.project_id,
        key_task_id=subtask.id,
        execution_plan_id=row.id,
        event_type="execution_plan_changed",
        source_type="execution_schedule",
        source_id=row.id,
        dedupe_key=f"operation_log:{log_row.id}:execution-plan-delete",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=False,
        status_before=before.get("status"),
        progress_summary=f"任务计划已删除：{row.title}",
    )
    db.commit()
    return {"ok": True}
