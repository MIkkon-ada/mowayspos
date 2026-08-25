from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import task_status as TS
from ..permissions import (
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
)
from ..services.key_task_execution import (
    completion_eligibility_dict,
    current_progress_dict,
    plan_summary_dict,
    record_execution_event,
    timeline_dicts,
)
from ..services.project_close import require_project_business_writable
from ..time_utils import utc_now
from .monthly_plans import sort_month_plans, to_month_plan_dict


router = APIRouter(prefix="/api/key-tasks", tags=["key-tasks"])


def _load_key_task(row_id: int, current_user: str, db: Session):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    parent = db.get(models.Task, row.task_id) if row else None
    project = db.get(models.Project, parent.project_id) if parent and parent.project_id else None
    if not row or not parent or not project or row.is_deleted or parent.is_deleted:
        raise HTTPException(404, "关键任务不存在")
    require_project_access(current_user, project.id, db)
    return current_user, context, project, parent, row


def _roles(context: dict, project_id: int, db: Session) -> set[str]:
    person_id = context.get("person_id")
    if not person_id:
        return set()
    return set(get_all_project_roles(int(person_id), project_id, db))


def _can_operate(context: dict, project_id: int, key_task: models.SubTask, db: Session) -> bool:
    if context.get("is_tech_admin"):
        return True
    if (context.get("name") or "") == (key_task.assignee or ""):
        return True
    return bool(_roles(context, project_id, db) & {"owner", "coordinator"})


def _can_edit_structure(context: dict, project_id: int, db: Session) -> bool:
    return bool(context.get("is_tech_admin") or _roles(context, project_id, db) & {"owner", "coordinator"})


def _people_names(person_ids: list[int] | None, db: Session) -> list[str]:
    ids = [int(value) for value in (person_ids or [])]
    if not ids:
        return []
    rows = db.query(models.Person).filter(models.Person.id.in_(ids)).all()
    names = {row.id: row.name for row in rows}
    return [names[person_id] for person_id in ids if person_id in names]


def _legacy_note_collaborators(notes: str | None) -> list[dict[str, str | None]]:
    first_line = (notes or "").splitlines()[0] if notes else ""
    match = re.match(r"^\s*(?:协同人|协助人)\s*[:：]\s*(.+?)\s*$", first_line)
    if not match:
        return []
    return [
        {"id": None, "name": name.strip()}
        for name in re.split(r"[、，,/／]", match.group(1))
        if name.strip()
    ]


@router.get("/{row_id}/execution-workspace")
def get_execution_workspace(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user, context, project, workstream, key_task = _load_key_task(
        row_id, current_user, db
    )
    schedules = (
        db.query(models.ExecutionSchedule)
        .filter(
            models.ExecutionSchedule.subtask_id == key_task.id,
            models.ExecutionSchedule.is_deleted.is_(False),
        )
        .all()
    )
    execution_plans = [to_month_plan_dict(row, db=db) for row in sort_month_plans(schedules)]
    achievements = (
        db.query(models.Achievement)
        .filter(models.Achievement.related_subtask_id == key_task.id)
        .order_by(models.Achievement.created_at.desc(), models.Achievement.id.desc())
        .limit(100)
        .all()
    )
    issues = (
        db.query(models.Issue)
        .filter(models.Issue.related_subtask_id == key_task.id)
        .order_by(models.Issue.updated_at.desc(), models.Issue.id.desc())
        .limit(100)
        .all()
    )
    collaborator_ids = [int(value) for value in (key_task.collaborator_ids or [])]
    collaborator_name_by_id = {
        row.id: row.name
        for row in db.query(models.Person)
        .filter(models.Person.id.in_(collaborator_ids))
        .all()
    } if collaborator_ids else {}
    can_operate = _can_operate(context, project.id, key_task, db)
    person_id = context.get("person_id")
    can_submit = bool(
        can_operate
        or (person_id and int(person_id) in set(key_task.collaborator_ids or []))
    )
    key_task_data = {
        "id": key_task.id,
        "title": key_task.title,
        "status": key_task.status,
        "owner": {"id": key_task.assignee_id, "name": key_task.assignee or ""},
        "collaborators": [
            {"id": person_id, "name": collaborator_name_by_id[person_id]}
            for person_id in collaborator_ids
            if person_id in collaborator_name_by_id
        ] or _legacy_note_collaborators(key_task.notes),
        "start_date": key_task.start_date.isoformat() if key_task.start_date else None,
        "due_kind": key_task.due_kind or "unknown",
        "due_date": key_task.due_date.isoformat() if key_task.due_date else None,
        "due_label": key_task.due_label or None,
        "due_reference_date": key_task.due_reference_date.isoformat() if key_task.due_reference_date else None,
        "plan_time": key_task.plan_time or workstream.plan_time or "",
        "completion_definition": key_task.completion_criteria or "",
        "risk_note": key_task.risk_note or "",
        "risk_marked_by": key_task.risk_marked_by or "",
        "risk_marked_at": key_task.risk_marked_at.isoformat() if key_task.risk_marked_at else None,
        "created_at": key_task.created_at.isoformat() if key_task.created_at else None,
        "source_type": "update_submission" if key_task.source_submission_id else "manual",
    }
    return {
        "key_task": key_task_data,
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status,
        },
        "workstream": {
            "id": workstream.id,
            "name": workstream.key_task,
        },
        "current_progress": current_progress_dict(db, key_task.id),
        "completion_eligibility": completion_eligibility_dict(db, key_task.id),
        "plan_summary": plan_summary_dict(db, key_task.id),
        "execution_plans": execution_plans,
        "achievements": [
            {
                "id": row.id,
                "name": row.name,
                "achievement_type": row.achievement_type,
                "status": row.status,
                "owner": row.owner,
                "version": row.version,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in achievements
        ],
        "issues": [
            {
                "id": row.id,
                "description": row.description,
                "issue_type": row.issue_type,
                "status": row.status,
                "priority": row.priority,
                "owner": row.owner,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in issues
        ],
        "timeline": timeline_dicts(db, key_task.id),
        "permissions": {
            "can_view": True,
            "can_operate": can_operate,
            "can_edit_key_task": _can_edit_structure(context, project.id, db),
            "can_manage_execution_plans": can_operate,
            "can_submit_update": can_submit,
            "can_confirm_completion": can_operate,
            "can_reopen": can_operate,
            "can_manage_risk": can_operate,
        },
    }


@router.post("/{row_id}/confirm-completion")
def confirm_key_task_completion(
    row_id: int,
    payload: schemas.KeyTaskCompletionRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user, context, project, _workstream, key_task = _load_key_task(
        row_id, current_user, db
    )
    require_project_business_writable(project.id, db)
    if not _can_operate(context, project.id, key_task, db):
        raise HTTPException(403, "permission denied")
    if TS.normalize(key_task.status) == TS.S_COMPLETED:
        return {"ok": True, "key_task": crud.to_dict(key_task)}
    eligibility = completion_eligibility_dict(db, key_task.id)
    if eligibility["state"] != "eligible":
        raise HTTPException(409, "任务计划尚未满足关键任务完成条件")

    before_status = key_task.status
    key_task.status = TS.S_COMPLETED
    now = utc_now()
    log_row = crud.log(
        db,
        current_user,
        "key_task_confirm_completion",
        "subtask",
        key_task.id,
        {"status": before_status},
        {"status": key_task.status},
        project_id=project.id,
        note=payload.note,
    )
    db.flush()
    record_execution_event(
        db,
        project_id=project.id,
        key_task_id=key_task.id,
        event_type="key_task_status_changed",
        source_type="key_task",
        source_id=key_task.id,
        dedupe_key=f"operation_log:{log_row.id}:key-task-complete",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=True,
        status_before=before_status,
        status_after=key_task.status,
        progress_summary="关键任务已由负责人确认完成",
        next_step=None,
        display_payload={"note": payload.note},
    )
    db.commit()
    db.refresh(key_task)
    return {"ok": True, "key_task": crud.to_dict(key_task)}


@router.post("/{row_id}/reopen")
def reopen_key_task(
    row_id: int,
    payload: schemas.KeyTaskReopenRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user, context, project, _workstream, key_task = _load_key_task(
        row_id, current_user, db
    )
    require_project_business_writable(project.id, db)
    if not _can_operate(context, project.id, key_task, db):
        raise HTTPException(403, "permission denied")
    if TS.normalize(key_task.status) != TS.S_COMPLETED:
        raise HTTPException(409, "只有已完成的关键任务可以重新打开")

    before_status = key_task.status
    key_task.status = TS.S_IN_PROGRESS
    now = utc_now()
    log_row = crud.log(
        db,
        current_user,
        "key_task_reopen",
        "subtask",
        key_task.id,
        {"status": before_status},
        {"status": key_task.status},
        project_id=project.id,
        note=payload.reason,
    )
    db.flush()
    record_execution_event(
        db,
        project_id=project.id,
        key_task_id=key_task.id,
        event_type="key_task_status_changed",
        source_type="key_task",
        source_id=key_task.id,
        dedupe_key=f"operation_log:{log_row.id}:key-task-reopen",
        actor_person_id=context.get("person_id"),
        actor_name=context.get("name") or current_user,
        occurred_at=now,
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=True,
        status_before=before_status,
        status_after=key_task.status,
        progress_summary="关键任务已重新打开",
        next_step=payload.reason,
        display_payload={"reason": payload.reason},
    )
    db.commit()
    db.refresh(key_task)
    return {"ok": True, "key_task": crud.to_dict(key_task)}


@router.patch("/{row_id}/risk")
def set_key_task_risk(
    row_id: int,
    payload: schemas.KeyTaskRiskRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user, context, project, _workstream, key_task = _load_key_task(
        row_id, current_user, db
    )
    require_project_business_writable(project.id, db)
    if not _can_operate(context, project.id, key_task, db):
        raise HTTPException(403, "permission denied")

    note = payload.risk_note.strip()
    before = {
        "risk_note": key_task.risk_note or "",
        "risk_marked_by": key_task.risk_marked_by or "",
        "risk_marked_at": key_task.risk_marked_at.isoformat() if key_task.risk_marked_at else None,
    }
    now = utc_now()
    key_task.risk_note = note
    key_task.risk_marked_by = current_user if note else ""
    key_task.risk_marked_at = now if note else None
    after = {
        "risk_note": key_task.risk_note,
        "risk_marked_by": key_task.risk_marked_by,
        "risk_marked_at": key_task.risk_marked_at.isoformat() if key_task.risk_marked_at else None,
    }
    if before != after:
        log_row = crud.log(
            db,
            current_user,
            "key_task_risk_updated",
            "subtask",
            key_task.id,
            before,
            after,
            project_id=project.id,
            note=note or "解除风险标记",
        )
        db.flush()
        record_execution_event(
            db,
            project_id=project.id,
            key_task_id=key_task.id,
            event_type="key_task_risk_updated",
            source_type="key_task",
            source_id=key_task.id,
            dedupe_key=f"operation_log:{log_row.id}:key-task-risk",
            actor_person_id=context.get("person_id"),
            actor_name=context.get("name") or current_user,
            occurred_at=now,
            confirmed_at=now,
            effective_at=now,
            affects_current_progress=False,
            progress_summary="关键任务已标记风险" if note else "关键任务风险标记已解除",
            next_step=note or None,
            display_payload={"risk_note": note, "has_risk": bool(note)},
        )
    db.commit()
    db.refresh(key_task)
    return {"ok": True, "key_task": crud.to_dict(key_task)}
