from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import get_current_user_name, get_user_context_from_db, require_login, require_project_access
from ..services.key_task_execution import record_execution_event
from ..time_utils import utc_now
from .execution_schedules import _parent, _require_write


router = APIRouter(tags=["monthly-plans"])
FINAL_STATUSES = {"已完成", "已取消"}
DISPLAY_STATUS_RANK = {"已延期": 0, "进行中": 1, "暂缓": 2, "未开始": 3, "已完成": 4, "已取消": 5}


def is_overdue(row: models.ExecutionSchedule, *, today: date | None = None) -> bool:
    today = today or utc_now().date()
    return bool(
        row.status not in FINAL_STATUSES
        and (row.due_kind == "exact" or (not row.due_kind and row.due_date is not None))
        and row.due_date
        and row.due_date < today
    )


def display_status(row: models.ExecutionSchedule, *, today: date | None = None) -> str:
    return "已延期" if is_overdue(row, today=today) else row.status


def month_plan_sort_key(row: models.ExecutionSchedule, *, today: date | None = None) -> tuple:
    status = display_status(row, today=today)
    return (
        DISPLAY_STATUS_RANK[status],
        (row.due_date or row.due_reference_date) is None,
        row.due_date or row.due_reference_date or date.max,
        row.sort_order,
        row.created_at or datetime.min,
        row.id,
    )


def sort_month_plans(rows: list[models.ExecutionSchedule], *, today: date | None = None) -> list[models.ExecutionSchedule]:
    return sorted(rows, key=lambda row: month_plan_sort_key(row, today=today))


def _project_member_ids(project_id: int, db: Session) -> set[int]:
    return {
        row.person_id
        for row in db.query(models.ProjectMember.person_id).filter(models.ProjectMember.project_id == project_id).all()
    }


def _people_by_id(person_ids: set[int], db: Session) -> dict[int, models.Person]:
    if not person_ids:
        return {}
    return {person.id: person for person in db.query(models.Person).filter(models.Person.id.in_(person_ids)).all()}


def _validate_people(project_id: int, assignee_id: int, collaborator_ids: list[int], db: Session) -> dict[int, models.Person]:
    requested_ids = {assignee_id, *collaborator_ids}
    if not requested_ids.issubset(_project_member_ids(project_id, db)):
        raise HTTPException(422, "负责人或协作人不属于该项目")
    people = _people_by_id(requested_ids, db)
    if requested_ids - set(people):
        raise HTTPException(422, "负责人或协作人不存在")
    return people


def to_month_plan_dict(row: models.ExecutionSchedule, *, today: date | None = None, db: Session | None = None) -> dict:
    data = {
        "id": row.id,
        "subtask_id": row.subtask_id,
        "plan_month": row.plan_month,
        "title": row.title,
        "expected_output": row.expected_output,
        "assignee": row.assignee,
        "assignee_id": row.assignee_id,
        "collaborator_ids": row.collaborator_ids or [],
        "status": row.status,
        "display_status": display_status(row, today=today),
        "is_overdue": is_overdue(row, today=today),
        "start_date": row.start_date,
        "due_kind": row.due_kind,
        "due_date": row.due_date,
        "due_label": row.due_label,
        "due_reference_date": row.due_reference_date,
        "completion_criteria": row.completion_criteria,
        "progress_note": row.progress_note,
        "risk_dependency": row.risk_dependency,
        "actual_output": row.actual_output,
        "delay_reason": row.delay_reason,
        "sort_order": row.sort_order,
        "is_archived": bool(row.is_archived),
        "latest_progress": row.progress_note or row.actual_output or "",
    }
    if db:
        people = _people_by_id(set(data["collaborator_ids"]), db)
        data["collaborators"] = [people[person_id].name for person_id in data["collaborator_ids"] if person_id in people]
    else:
        data["collaborators"] = []
    return data


def _month_plan_rows(subtask_id: int, db: Session, month: str | None = None) -> list[models.ExecutionSchedule]:
    query = db.query(models.ExecutionSchedule).filter(
        models.ExecutionSchedule.subtask_id == subtask_id,
        models.ExecutionSchedule.plan_type == "month",
        models.ExecutionSchedule.is_deleted.is_(False),
    )
    if month:
        query = query.filter(models.ExecutionSchedule.plan_month == month)
    return query.all()


def _ensure_can_view(task: models.Task, current_user: str, db: Session) -> None:
    if not task.project_id:
        raise HTTPException(403, "permission denied")
    require_project_access(current_user, task.project_id, db)


@router.get("/api/subtasks/{subtask_id}/monthly-plans")
def list_monthly_plans(
    subtask_id: int,
    month: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    subtask = db.get(models.SubTask, subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not subtask or not task or subtask.is_deleted or task.is_deleted:
        raise HTTPException(404, "关键任务不存在")
    _ensure_can_view(task, current_user, db)
    rows = sort_month_plans(_month_plan_rows(subtask_id, db, month))
    return [to_month_plan_dict(row, db=db) for row in rows]


@router.post("/api/subtasks/{subtask_id}/monthly-plans")
def create_monthly_plan(
    subtask_id: int,
    payload: schemas.MonthPlanCreatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    subtask = db.get(models.SubTask, subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not subtask or not task or subtask.is_deleted or task.is_deleted:
        raise HTTPException(404, "关键任务不存在")
    _require_write(current_user, context, subtask, task, db)
    if subtask.status == "已完成":
        raise HTTPException(409, "已完成的关键任务必须先重新打开，才能新增任务计划")
    people = _validate_people(task.project_id, payload.assignee_id, payload.collaborator_ids, db)
    data = payload.model_dump()
    data["assignee"] = people[payload.assignee_id].name
    row = models.ExecutionSchedule(
        subtask_id=subtask_id,
        plan_type="month",
        created_by=current_user,
        updated_by=current_user,
        **data,
    )
    db.add(row)
    db.flush()
    log_row = crud.log(db, current_user, "monthly_plan_create", "execution_schedule", row.id, {}, crud.to_dict(row), project_id=task.project_id)
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
    db.commit()
    db.refresh(row)
    return to_month_plan_dict(row, db=db)


@router.patch("/api/monthly-plans/{plan_id}")
def update_monthly_plan(
    plan_id: int,
    payload: schemas.MonthPlanUpdatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, plan_id)
    if not row or row.is_deleted or row.plan_type != "month":
        raise HTTPException(404, "任务计划不存在")
    subtask, task = _parent(row, db)
    _require_write(current_user, context, subtask, task, db)
    changes = payload.model_dump(exclude_unset=True)
    if is_overdue(row) and ({"due_date", "plan_month"} & set(changes)) and not str(changes.get("delay_reason") or "").strip():
        raise HTTPException(422, "调整已延期计划时必须填写延期原因")
    candidate_data = {
        "plan_month": changes.get("plan_month", row.plan_month),
        "title": changes.get("title", row.title),
        "expected_output": changes.get("expected_output", row.expected_output),
        "assignee_id": changes.get("assignee_id", row.assignee_id),
        "collaborator_ids": changes.get("collaborator_ids", row.collaborator_ids or []),
        "status": changes.get("status", row.status),
        "start_date": changes.get("start_date", row.start_date),
        "due_kind": changes.get("due_kind", row.due_kind),
        "due_date": changes.get("due_date", row.due_date),
        "due_label": changes.get("due_label", row.due_label),
        "due_reference_date": changes.get("due_reference_date", row.due_reference_date),
        "completion_criteria": changes.get("completion_criteria", row.completion_criteria),
        "progress_note": changes.get("progress_note", row.progress_note),
        "risk_dependency": changes.get("risk_dependency", row.risk_dependency),
        "actual_output": changes.get("actual_output", row.actual_output),
        "delay_reason": changes.get("delay_reason", row.delay_reason),
        "sort_order": changes.get("sort_order", row.sort_order),
        "is_archived": changes.get("is_archived", row.is_archived),
    }
    candidate = schemas.MonthPlanCreatePayload(**candidate_data)
    people = _validate_people(task.project_id, candidate.assignee_id, candidate.collaborator_ids, db)
    before = crud.to_dict(row)
    crud.update_model(row, candidate.model_dump())
    row.assignee = people[candidate.assignee_id].name
    row.updated_by = current_user
    log_row = crud.log(db, current_user, "monthly_plan_update", "execution_schedule", row.id, before, crud.to_dict(row), project_id=task.project_id)
    db.flush()
    now = utc_now()
    progress_changed = bool(
        ("progress_note" in changes and (row.progress_note or "").strip())
        or ("actual_output" in changes and (row.actual_output or "").strip())
    )
    status_changed = before.get("status") != row.status
    record_execution_event(
        db,
        project_id=task.project_id,
        key_task_id=subtask.id,
        execution_plan_id=row.id,
        event_type="execution_plan_status_changed" if status_changed else "execution_plan_changed",
        source_type="execution_schedule",
        source_id=row.id,
        dedupe_key=f"operation_log:{log_row.id}:execution-plan-update",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=progress_changed,
        status_before=before.get("status"),
        status_after=row.status,
        progress_summary=(row.progress_note or row.actual_output or f"任务计划已更新：{row.title}"),
    )
    db.commit()
    db.refresh(row)
    return to_month_plan_dict(row, db=db)


@router.delete("/api/monthly-plans/{plan_id}")
def delete_monthly_plan(
    plan_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.ExecutionSchedule, plan_id)
    if not row or row.is_deleted or row.plan_type != "month":
        raise HTTPException(404, "任务计划不存在")
    subtask, task = _parent(row, db)
    _require_write(current_user, context, subtask, task, db)
    before = crud.to_dict(row)
    row.is_deleted = True
    row.updated_by = current_user
    log_row = crud.log(db, current_user, "monthly_plan_delete", "execution_schedule", row.id, before, {"is_deleted": True}, project_id=task.project_id)
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
