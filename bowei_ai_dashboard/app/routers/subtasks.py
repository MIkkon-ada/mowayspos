import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import text

from .. import crud, models, schemas
from ..database import get_db
from ..domain import task_status as TS
from ..domain import submission_result_type as RT
from ..permissions import (
    PROJECT_ROLE_COORDINATOR,
    PROJECT_ROLE_OWNER,
    can_view_project,
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
)
from ..time_utils import utc_now
from ..services.project_resolution import resolve_project_context
from ..archived_guard import require_project_not_archived

router = APIRouter(tags=["subtasks"])  # endpoint 不变；业务语义：KeyTask/关键任务 CRUD
_TRASH_ROLES = {"owner"}


def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _task_project_name(task: models.Task, db: Session) -> str:
    resolved = resolve_project_context(
        db,
        project_id=task.project_id,
        special_project=task.special_project or "",
    )
    # Display-only fallback: the parent task's project_id still owns the subtask.
    return resolved["project_name"] or task.special_project or ""


def _get_task_project_id(task: models.Task, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=task.project_id,
        special_project=task.special_project or "",
    )["project_id"]


def _check_owner_write(context: dict, task: models.Task, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm and set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"}:
            return
    raise HTTPException(403, "permission denied")


def _check_trash_access(context: dict, task: models.Task, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm and set(get_all_project_roles(person_id, project_id, db)) & _TRASH_ROLES:
            return
    raise HTTPException(403, "permission denied")


def _can_edit_subtask(context: dict, row: models.SubTask, task: models.Task, db: Session) -> bool:
    if context.get("is_tech_admin"):
        return True
    current_name = context.get("name") or ""
    if current_name and current_name == row.assignee:
        return True
    project_id = task.project_id
    if project_id is None:
        return False
    person_id = context.get("person_id")
    if person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm:
            return bool(set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"})
    return False


def _is_privileged_write(context: dict, task: models.Task, db: Session) -> bool:
    """True if the current user is owner, coordinator, or tech_admin for this task's project.
    Returns False when the caller is only the subtask assignee (member role)."""
    if context.get("is_tech_admin"):
        return True
    project_id = task.project_id
    if project_id is None:
        return False
    person_id = context.get("person_id")
    if person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm:
            return bool(set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"})
    return False


def _check_project_member_create(context: dict, task: models.Task, db: Session) -> None:
    """只有 owner、coordinator 或 tech_admin 才能创建成员子任务。"""
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm and set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"}:
            return
    raise HTTPException(403, "permission denied")


def _check_subtask_struct_write(context: dict, task: models.Task, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is None:
        raise HTTPException(403, "permission denied")
    has_pm = db.execute(
        text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
        {"pid": project_id},
    ).fetchone()
    if has_pm and set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"}:
        return
    raise HTTPException(403, "permission denied")


def _check_subtask_delete_access(context: dict, task: models.Task, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is None:
        raise HTTPException(403, "permission denied")
    has_pm = db.execute(
        text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
        {"pid": project_id},
    ).fetchone()
    if has_pm and set(get_all_project_roles(person_id, project_id, db)) & {"owner", "coordinator"}:
        return
    raise HTTPException(403, "permission denied")


def _check_subtask_restore_access(context: dict, task: models.Task, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    person_id = context.get("person_id")
    if person_id is None:
        raise HTTPException(403, "permission denied")
    has_pm = db.execute(
        text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
        {"pid": project_id},
    ).fetchone()
    if has_pm and "owner" in set(get_all_project_roles(person_id, project_id, db)):
        return
    raise HTTPException(403, "permission denied")


def _sync_parent_task_status(task: models.Task, db: Session, current_user: str) -> None:
    subtasks = db.query(models.SubTask).filter_by(task_id=task.id).filter(models.SubTask.is_deleted.is_(False)).all()
    next_status = TS.derive_parent_status(task.status, [row.status or "" for row in subtasks])
    if TS.normalize(task.status) == next_status:
        return
    before_status = task.status
    task.status = next_status
    task.edit_count = (task.edit_count or 0) + 1
    crud.log(
        db,
        current_user,
        "task_sync_status_from_subtasks",
        "task",
        task.id,
        {"status": before_status},
        {"status": next_status},
        project_id=_get_task_project_id(task, db),
    )


def _soft_delete_subtask(row: models.SubTask, operator: str, batch_id: str, parent_id: int, reason: str = "") -> None:
    row.is_deleted = True
    row.deleted_at = utc_now()
    row.deleted_by = operator
    row.delete_reason = reason or ""
    row.delete_batch_id = batch_id
    row.deleted_by_parent_id = parent_id


def _restore_subtask(row: models.SubTask) -> None:
    row.is_deleted = False
    row.deleted_at = None
    row.deleted_by = ""
    row.delete_reason = ""
    row.delete_batch_id = ""
    row.deleted_by_parent_id = None


@router.get("/api/subtasks")
def list_subtasks_global(
    assignee: str | None = None,
    project_id: int | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """按 assignee / project_id 过滤子任务列表（全局接口）。"""
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    if project_id is None:
        _require_global_read_scope(context)
    else:
        require_project_access(current_user, project_id, db)
    q = (
        db.query(models.SubTask, models.Task)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
        )
    )
    if assignee:
        q = q.filter(models.SubTask.assignee == assignee)
    if project_id is not None:
        # project_id is the primary read filter; assignee only narrows within the project scope.
        q = q.filter(models.Task.project_id == project_id)
    rows = q.order_by(models.Task.id.asc(), models.SubTask.created_at.asc()).all()
    result = []
    for subtask, task in rows:
        d = crud.to_dict(subtask)
        d["parent_key_task"] = task.key_task
        d["parent_task_id"] = task.id
        d["parent_project_id"] = task.project_id
        # parent_special_project is kept only for legacy display compatibility.
        d["parent_special_project"] = _task_project_name(task, db)
        result.append(d)
    return result


@router.get("/api/tasks/{task_id}/subtasks")
def list_subtasks(
    task_id: int,
    deleted: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if bool(getattr(task, "is_deleted", False)) and not deleted:
        raise HTTPException(404, "task not found")
    project_id = _get_task_project_id(task, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    if deleted:
        _check_trash_access(context, task, db)
    rows = (
        db.query(models.SubTask)
        .filter_by(task_id=task_id)
        .filter(models.SubTask.is_deleted.is_(bool(deleted)))
        .order_by(models.SubTask.created_at.asc())
        .all()
    )
    return [crud.to_dict(r) for r in rows]


@router.get("/api/subtasks/{row_id}/detail")
def get_subtask_detail(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """返回子任务详情，供前端详情抽屉使用。"""
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "subtask not found")

    parent = db.get(models.Task, row.task_id)
    if parent:
        project_id = _get_task_project_id(parent, db)
        if project_id is not None:
            require_project_access(current_user, project_id, db)
        elif not (context.get("is_tech_admin") or context.get("is_ceo")):
            raise HTTPException(403, "permission denied")

    result = crud.to_dict(row)

    if parent:
        result["parent_task"] = {
            "id": parent.id,
            "key_task": parent.key_task,
            # legacy display fallback only; access control still uses parent.project_id.
            "special_project": _task_project_name(parent, db),
        }

    if row.source_submission_id:
        sub = db.get(models.UpdateSubmission, row.source_submission_id)
        if sub:
            import json as _json
            ai_raw = {}
            try:
                ai_raw = _json.loads(sub.ai_result_json or "{}")
            except Exception:
                pass
            completed = ai_raw.get("completed_items") or []
            result["source_submission"] = {
                "id": sub.id,
                "submitter": sub.submitter,
                "source_type": sub.source_type,
                "title": sub.title,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "summary": ai_raw.get("summary") or ai_raw.get("related_task") or "",
                "completed_items": completed if isinstance(completed, list) else [],
                "transcript_text": (sub.transcript_text or "")[:500],
            }

    achievements = (
        db.query(models.Achievement)
        .filter(models.Achievement.related_task_id == row.task_id)
        .order_by(models.Achievement.created_at.desc())
        .limit(10)
        .all()
    )
    result["related_achievements"] = [
        {
            "id": a.id,
            "name": a.name,
            "achievement_type": a.achievement_type,
            "status": a.status,
            "owner": a.owner,
            "version": a.version,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in achievements
    ]

    issues = (
        db.query(models.Issue)
        .filter(models.Issue.related_task_id == row.task_id)
        .order_by(models.Issue.created_at.desc())
        .limit(10)
        .all()
    )
    result["related_issues"] = [
        {
            "id": i.id,
            "description": i.description,
            "issue_type": i.issue_type,
            "status": i.status,
            "priority": i.priority,
            "owner": i.owner,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in issues
    ]

    return result


@router.post("/api/tasks/{task_id}/subtasks")
def create_subtask(
    task_id: int,
    payload: schemas.SubTaskPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if bool(getattr(task, "is_deleted", False)):
        raise HTTPException(409, "task is deleted")
    _check_subtask_struct_write(context, task, db)
    require_project_not_archived(_get_task_project_id(task, db), db)

    data = payload.model_dump()
    if (data.get("assignee") or "").strip() and TS.normalize(data.get("status", "")) == TS.S_NOT_STARTED:
        data["status"] = TS.S_IN_PROGRESS

    parent_was_completed = TS.normalize(task.status) == TS.S_COMPLETED

    row = models.SubTask(task_id=task_id, **data)
    from ..services.notify import person_id_for_name as _pid_for_name
    row.assignee_id = _pid_for_name(row.assignee or "", db)
    db.add(row)
    db.flush()
    crud.log(db, current_user, "subtask_create", "subtask", row.id, {}, crud.to_dict(row), project_id=_get_task_project_id(task, db))

    if parent_was_completed:
        before_task_status = task.status
        task.status = TS.S_IN_PROGRESS
        task.edit_count = (task.edit_count or 0) + 1
        crud.log(
            db,
            current_user,
            "task_reopen_for_subtask",
            "task",
            task.id,
            {"status": before_task_status},
            {"status": TS.S_IN_PROGRESS},
            project_id=_get_task_project_id(task, db),
            note="auto reopen after creating subtask",
        )

    _sync_parent_task_status(task, db, current_user)

    if row.assignee and row.assignee != current_user:
        from ..services.notify import send as _notify, person_name_for_account, person_id_for_name, person_id_for_account
        caller_name = person_name_for_account(current_user, db)
        caller_id = person_id_for_account(current_user, db)
        assignee_id = person_id_for_name(row.assignee, db)
        if row.assignee != caller_name and assignee_id != caller_id:
            project_id = _get_task_project_id(task, db)
            _notify(
                db,
                recipient_id=assignee_id,
                recipient=row.assignee,
                ntype="subtask_assigned",
                title=f"New subtask: {row.title}",
                body=f"Task: {task.key_task}; assigned by: {caller_name}",
                link=f"/project/{project_id}/mytasks" if project_id else "",
                project_id=project_id,
            )

    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


@router.patch("/api/subtasks/{row_id}")
def update_subtask(
    row_id: int,
    payload: schemas.SubTaskPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    if not row:
        raise HTTPException(404, "subtask not found")
    task = db.get(models.Task, row.task_id)
    if not task:
        raise HTTPException(404, "parent task not found")
    if bool(getattr(row, "is_deleted", False)):
        raise HTTPException(404, "subtask not found")
    if bool(getattr(task, "is_deleted", False)):
        raise HTTPException(409, "parent task is deleted")

    _check_subtask_struct_write(context, task, db)
    require_project_not_archived(_get_task_project_id(task, db), db)

    before = crud.to_dict(row)
    before_assignee = (row.assignee or "").strip()
    crud.update_model(row, payload.model_dump())
    from ..services.notify import person_id_for_name as _pid_for_name
    row.assignee_id = _pid_for_name(row.assignee or "", db)

    if not before_assignee and (row.assignee or "").strip():
        if TS.normalize(row.status) == TS.S_NOT_STARTED:
            row.status = TS.S_IN_PROGRESS

    crud.log(db, current_user, "subtask_update", "subtask", row.id, before, payload.model_dump())
    _sync_parent_task_status(task, db, current_user)
    db.commit()
    return crud.to_dict(row)


@router.patch("/api/subtasks/{row_id}/status")
def patch_subtask_status(
    row_id: int,
    payload: schemas.StatusRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    if not row:
        raise HTTPException(404, "subtask not found")
    task = db.get(models.Task, row.task_id)
    if not task:
        raise HTTPException(404, "parent task not found")
    if bool(getattr(row, "is_deleted", False)):
        raise HTTPException(404, "subtask not found")
    if bool(getattr(task, "is_deleted", False)):
        raise HTTPException(409, "parent task is deleted")

    _check_subtask_struct_write(context, task, db)
    require_project_not_archived(_get_task_project_id(task, db), db)

    before_status = row.status or ""
    row.status = payload.status
    project_id = _get_task_project_id(task, db)
    crud.log(
        db,
        current_user,
        "subtask_update_status",
        "subtask",
        row.id,
        {"status": before_status},
        {"status": payload.status},
        project_id=project_id,
    )
    if TS.normalize(payload.status) == TS.S_COMPLETED and task.owner_id:
        from ..services.notify import send as _notify, person_name_for_account, person_id_for_account
        caller_name = person_name_for_account(current_user, db)
        caller_id = person_id_for_account(current_user, db)
        if task.owner_id != caller_id:
            _notify(
                db,
                recipient_id=task.owner_id,
                ntype="subtask_completed",
                title=f"Subtask completed: {row.title}",
                body=f"Task: {task.key_task}; completed by: {caller_name}",
                link=f"/project/{project_id}/mytasks" if project_id else "",
                project_id=project_id,
            )
    _sync_parent_task_status(task, db, current_user)
    db.commit()
    return crud.to_dict(row)


@router.delete("/api/subtasks/{row_id}")
def delete_subtask(
    row_id: int,
    reason: str = "",
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    if not row:
        raise HTTPException(404, "subtask not found")
    task = db.get(models.Task, row.task_id)
    if not task:
        raise HTTPException(404, "parent task not found")
    _check_subtask_delete_access(context, task, db)
    require_project_not_archived(_get_task_project_id(task, db), db)
    if bool(getattr(row, "is_deleted", False)):
        raise HTTPException(409, "subtask already deleted")
    before = crud.to_dict(row)
    batch_id = row.delete_batch_id or f"subtask-{row.id}"
    _soft_delete_subtask(row, current_user, batch_id, task.id, reason)
    crud.log(
        db,
        current_user,
        "subtask_delete",
        "subtask",
        row.id,
        before,
        crud.to_dict(row),
        project_id=_get_task_project_id(task, db),
        note=reason or "moved to recycle bin",
    )
    db.flush()
    _sync_parent_task_status(task, db, current_user)
    db.commit()
    return {"ok": True}


@router.post("/api/subtasks/{row_id}/restore")
def restore_subtask(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.SubTask, row_id)
    if not row:
        raise HTTPException(404, "subtask not found")
    task = db.get(models.Task, row.task_id)
    if not task:
        raise HTTPException(404, "parent task not found")
    _check_subtask_restore_access(context, task, db)
    require_project_not_archived(_get_task_project_id(task, db), db)
    if not bool(getattr(row, "is_deleted", False)):
        raise HTTPException(409, "subtask is not deleted")
    if bool(getattr(task, "is_deleted", False)):
        raise HTTPException(409, "parent task is deleted")

    before = crud.to_dict(row)
    _restore_subtask(row)
    crud.log(
        db,
        current_user,
        "subtask_restore",
        "subtask",
        row.id,
        before,
        crud.to_dict(row),
        project_id=_get_task_project_id(task, db),
    )
    db.flush()
    _sync_parent_task_status(task, db, current_user)
    db.commit()
    return {"ok": True, "subtask": crud.to_dict(row)}
