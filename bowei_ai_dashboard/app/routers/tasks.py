from fastapi import APIRouter, Depends, HTTPException
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import task_status as TS
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
from ..services.extractor import extract_tasks as _extract_tasks
from ..services.notify import person_id_for_name as _pid_for_name
from ..services.project_resolution import resolve_project_context
from ..archived_guard import require_project_not_archived

router = APIRouter(prefix="/api/tasks", tags=["tasks"])  # endpoint 不变；业务语义：Workstream/重点工作 CRUD


# ── 写权限：owner 或 coordinator 可直接编辑已入库事项（Path B）────
_WRITE_ROLES = {"owner", "coordinator"}
_TRASH_ROLES = {"owner"}


def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _check_write(context: dict, project_id: int | None, proj_name: str, db: Session) -> None:
    """只有 super_admin、owner 或 coordinator 才能写入任务。"""
    if context.get("is_tech_admin"):
        return

    person_id = context.get("person_id")
    if project_id is not None and person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm:
            if set(get_all_project_roles(person_id, project_id, db)) & _WRITE_ROLES:
                return
            raise HTTPException(403, "permission denied - only project owner, coordinator or tech admin can write tasks")

    raise HTTPException(403, "permission denied - only project owner, coordinator or tech admin can write tasks")


def _check_batch_write(context: dict, project_id: int | None, proj_name: str, db: Session) -> None:
    """批量导入任务仅允许 owner 或 tech_admin。"""
    if context.get("is_tech_admin"):
        return

    person_id = context.get("person_id")
    if project_id is not None and person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm and "owner" in set(get_all_project_roles(person_id, project_id, db)):
            return

    raise HTTPException(403, "permission denied - only project owner or tech admin can batch import tasks")


def _check_trash_access(context: dict, project_id: int | None, proj_name: str, db: Session) -> None:
    """回收站相关操作仅允许 owner 或 tech_admin。"""
    if context.get("is_tech_admin"):
        return

    person_id = context.get("person_id")
    if project_id is not None and person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm:
            if set(get_all_project_roles(person_id, project_id, db)) & _TRASH_ROLES:
                return
            raise HTTPException(403, "permission denied - only project owner or tech admin can access recycle-bin actions")

    raise HTTPException(403, "permission denied - only project owner or tech admin can access recycle-bin actions")


def _row_project_id(row: models.Task, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]


def _row_project_name(row: models.Task, db: Session) -> str:
    resolved = resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )
    # Display-only fallback: project_id remains the ownership source.
    return resolved["project_name"] or row.special_project or ""


def _write_task_project_id(row: models.Task, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]


def _assert_can_complete_from_subtasks(row: models.Task, db: Session) -> None:
    subtasks = db.query(models.SubTask).filter_by(task_id=row.id).filter(models.SubTask.is_deleted.is_(False)).all()
    if not subtasks:
        raise HTTPException(409, "当前关键任务没有可完成的子任务")
    if not all(TS.is_completed(sub.status) for sub in subtasks):
        raise HTTPException(409, "子任务未全部完成，不能关闭关键任务")


def _check_close_task(context: dict, project_id: int | None, proj_name: str, db: Session) -> None:
    """关闭关键任务仅允许 owner 或 tech_admin。"""
    if context.get("is_tech_admin"):
        return
    person_id = context.get("person_id")
    if project_id is not None and person_id is not None:
        has_pm = db.execute(
            text("SELECT 1 FROM project_members WHERE project_id = :pid LIMIT 1"),
            {"pid": project_id},
        ).fetchone()
        if has_pm:
            if "owner" in set(get_all_project_roles(person_id, project_id, db)):
                return
            raise HTTPException(403, "permission denied - only project owner or tech admin can close key tasks")
    raise HTTPException(403, "permission denied - only project owner or tech admin can close key tasks")


def _task_is_deleted(row: models.Task) -> bool:
    return bool(getattr(row, "is_deleted", False))


def _soft_delete_task(row: models.Task, operator: str, reason: str = "", batch_id: str | None = None) -> str:
    batch = batch_id or uuid4().hex
    row.is_deleted = True
    row.deleted_at = utc_now()
    row.deleted_by = operator
    row.delete_reason = reason or ""
    row.delete_batch_id = batch
    return batch


def _restore_task(row: models.Task) -> None:
    row.is_deleted = False
    row.deleted_at = None
    row.deleted_by = ""
    row.delete_reason = ""
    row.delete_batch_id = ""


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


# ── 端点 ──────────────────────────────────────────────────────

@router.get("")
def list_tasks(
    project_id: int | None = None,
    special_project: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    month: str | None = None,
    deleted: bool = False,
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

    if deleted and effective_project_id is None and not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")

    q = db.query(models.Task)
    q = q.filter(models.Task.is_deleted.is_(bool(deleted)))

    if effective_project_id is None and not special_project:
        # Legacy fallback for old global listings where only special_project existed.
        active_proj_names = db.query(models.Project.name).filter(models.Project.status != "archived")
        q = q.filter(models.Task.special_project.in_(active_proj_names))

    if effective_project_id is not None:
        proj_name = crud.get_project_name_by_id(effective_project_id, db)
        if deleted:
            _check_trash_access(context, effective_project_id, proj_name, db)
        q = q.filter(models.Task.project_id == effective_project_id)

    if owner:
        q = q.filter(models.Task.owner == owner)
    if status:
        q = q.filter(models.Task.status == status)
    if month:
        q = q.filter(models.Task.plan_time.like(f"{month}%"))
    if deleted:
        rows = q.order_by(models.Task.deleted_at.desc().nullslast(), models.Task.created_at.desc()).all()
    else:
        rows = q.order_by(models.Task.created_at.asc()).all()
    return [crud.to_dict(r) for r in rows]


@router.post("")
def create_task(
    payload: schemas.TaskPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)

    resolution = resolve_project_context(
        db,
        project_id=payload.project_id,
        special_project=payload.special_project,
    )
    effective_project_id = resolution["project_id"]
    if payload.project_id is None:
        if not context.get("is_tech_admin"):
            raise HTTPException(422, "project_id is required")
        if effective_project_id is None:
            raise HTTPException(422, "project_id is required")
    elif not resolution["is_valid"]:
        raise HTTPException(404, "project not found")

    proj_name = crud.get_project_name_by_id(effective_project_id, db) or ""
    _check_write(context, effective_project_id, proj_name, db)
    require_project_not_archived(effective_project_id, db)

    data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    row = models.Task(**data)
    row.project_id = effective_project_id
    row.owner_id = _pid_for_name(row.owner or "", db)
    if effective_project_id is not None:
        # Keep special_project as a display mirror of the resolved project, never a competing owner key.
        row.special_project = resolution["project_name"] or proj_name
    elif not row.special_project:
        row.special_project = payload.special_project or ""
    db.add(row)
    db.flush()
    crud.log(db, current_user, "task_create", "task", row.id, {}, crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return crud.to_dict(row)

@router.get("/{row_id}")
def get_task(
    row_id: int,
    deleted: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    if _task_is_deleted(row) != bool(deleted):
        raise HTTPException(404, "task not found")
    project_id = _row_project_id(row, db)
    project_name = _row_project_name(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    if deleted:
        # Recycle-bin access still uses the resolved project_id; project name is only for compatibility checks.
        _check_trash_access(context, project_id, project_name, db)
    return crud.to_dict(row)


@router.put("/{row_id}")
def update_task(
    row_id: int,
    payload: schemas.TaskPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")

    project_id = _write_task_project_id(row, db)
    project_name = crud.get_project_name_by_id(project_id, db) if project_id is not None else ""
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    _check_write(context, project_id, project_name, db)
    require_project_not_archived(project_id, db)

    incoming_resolution = resolve_project_context(
        db,
        project_id=payload.project_id,
        special_project=payload.special_project,
    )
    if payload.project_id is not None and not incoming_resolution["is_valid"]:
        raise HTTPException(404, "project not found")

    target_project_id = project_id
    if payload.project_id is not None:
        target_project_id = incoming_resolution["project_id"]
    elif payload.special_project and incoming_resolution["is_valid"]:
        target_project_id = incoming_resolution["project_id"]

    closing = TS.normalize(payload.status) == TS.S_COMPLETED
    if closing:
        _check_close_task(context, project_id, project_name, db)
        _assert_can_complete_from_subtasks(row, db)

    before = crud.to_dict(row)
    update_data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    if "status" in update_data:
        update_data["status"] = TS.normalize(update_data["status"])
    crud.update_model(row, update_data)
    row.owner_id = _pid_for_name(row.owner or "", db)
    if target_project_id is not None:
        row.project_id = target_project_id
        row.special_project = crud.get_project_name_by_id(target_project_id, db) or incoming_resolution["project_name"] or project_name
    elif payload.special_project:
        row.special_project = payload.special_project.strip()
    row.edit_count = (row.edit_count or 0) + 1
    effective_pid = row.project_id or project_id
    action = "task_close" if closing else "task_update"
    crud.log(db, current_user, action, "task", row.id, before, payload.model_dump(), project_id=effective_pid)
    db.commit()
    return crud.to_dict(row)

@router.delete("/{row_id}")
def delete_task(
    row_id: int,
    reason: str = "",
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    if _task_is_deleted(row):
        raise HTTPException(409, "task already deleted")

    project_id = _write_task_project_id(row, db)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    _check_trash_access(context, project_id, crud.get_project_name_by_id(project_id, db) if project_id is not None else "", db)
    require_project_not_archived(project_id, db)

    before = crud.to_dict(row)
    batch_id = _soft_delete_task(row, current_user, reason)
    crud.log(db, current_user, "task_delete", "task", row_id, before, crud.to_dict(row),
             project_id=project_id, note=reason or "任务删除")

    child_rows = (
        db.query(models.SubTask)
        .filter(models.SubTask.task_id == row_id, models.SubTask.is_deleted.is_(False))
        .all()
    )
    for child in child_rows:
        child_before = crud.to_dict(child)
        _soft_delete_subtask(child, current_user, batch_id, row_id, reason)
        crud.log(db, current_user, "subtask_delete", "subtask", child.id, child_before, crud.to_dict(child),
                 project_id=project_id, note=reason or "子任务删除")

    db.commit()
    return {"ok": True}

@router.patch("/{row_id}/status")
def patch_status(
    row_id: int,
    payload: schemas.StatusRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    if _task_is_deleted(row):
        raise HTTPException(409, "task is deleted")

    project_id = _write_task_project_id(row, db)
    project_name = crud.get_project_name_by_id(project_id, db) if project_id is not None else ""
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    _check_write(context, project_id, project_name, db)
    require_project_not_archived(project_id, db)

    closing = TS.normalize(payload.status) == TS.S_COMPLETED
    if closing:
        _check_close_task(context, project_id, project_name, db)
        _assert_can_complete_from_subtasks(row, db)

    before_status = row.status
    row.status = TS.normalize(payload.status)
    row.edit_count = (row.edit_count or 0) + 1
    action = "task_close" if closing else "task_update_status"
    crud.log(db, current_user, action, "task", row.id,
             {"status": before_status}, {"status": payload.status},
             project_id=project_id)
    db.commit()
    return crud.to_dict(row)

@router.post("/{row_id}/restore")
def restore_task(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    if not _task_is_deleted(row):
        raise HTTPException(409, "task is not deleted")

    project_id = _write_task_project_id(row, db)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    _check_trash_access(context, project_id, crud.get_project_name_by_id(project_id, db) if project_id is not None else "", db)
    require_project_not_archived(project_id, db)

    before = crud.to_dict(row)
    batch_id = row.delete_batch_id or ""
    _restore_task(row)
    crud.log(db, current_user, "task_restore", "task", row.id, before, crud.to_dict(row), project_id=project_id)

    child_rows = (
        db.query(models.SubTask)
        .filter(
            models.SubTask.task_id == row.id,
            models.SubTask.is_deleted.is_(True),
            models.SubTask.deleted_by_parent_id == row.id,
        )
        .all()
    )
    for child in child_rows:
        if batch_id and child.delete_batch_id != batch_id:
            continue
        child_before = crud.to_dict(child)
        _restore_subtask(child)
        crud.log(
            db,
            current_user,
            "subtask_restore",
            "subtask",
            child.id,
            child_before,
            crud.to_dict(child),
            project_id=project_id,
        )

    db.commit()
    return {"ok": True, "task": crud.to_dict(row)}

@router.get("/{row_id}/logs")
def get_task_logs(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    project_id = _row_project_id(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    logs = (
        db.query(models.OperationLog)
        .filter_by(target_type="task", target_id=row_id)
        .order_by(models.OperationLog.created_at.asc())
        .limit(20)
        .all()
    )
    return [
        {
            "action": r.action,
            "operator": r.operator,
            "note": r.note or "",
            "created_at": r.created_at.strftime("%m-%d %H:%M") if r.created_at else "",
        }
        for r in logs
    ]


@router.get("/{row_id}/updates")
def get_task_updates(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Task, row_id)
    if not row:
        raise HTTPException(404, "task not found")
    project_id = _row_project_id(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    rows = (
        db.query(models.UpdateSubmission)
        .filter_by(related_task_id=row_id)
        .order_by(models.UpdateSubmission.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": r.id,
            "submitter": r.submitter,
            "transcript_text": (r.transcript_text or "")[:120],
            "created_at": r.created_at.strftime("%m-%d %H:%M") if r.created_at else "",
        }
        for r in rows
    ]


@router.post("/extract")
def extract_outline(
    payload: schemas.TaskOutlineExtractRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """AI task outline extraction only returns draft suggestions."""
    current_user = require_login(current_user, db)
    if payload.project_id is not None:
        require_project_access(current_user, payload.project_id, db)
    try:
        result = _extract_tasks(payload.text, payload.llm_provider, payload.project_names)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    return result

@router.post("/batch")
def batch_create(
    payload: schemas.TaskBatchCreateRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """批量创建任务（大纲导入）。仅 owner/coordinator/super_admin 可调用。"""
    context = get_user_context_from_db(current_user, db)
    canonical_project_name = crud.get_project_name_by_id(payload.project_id, db) or ""
    _check_batch_write(context, payload.project_id, canonical_project_name, db)
    require_project_not_archived(payload.project_id, db)

    created = []
    for draft in payload.tasks:
        if not draft.key_task.strip():
            continue
        row = models.Task(
            project_id=payload.project_id,
            special_project=canonical_project_name,
            key_task=draft.key_task,
            owner=draft.owner,
            owner_id=_pid_for_name(draft.owner or "", db),
            coordinator=draft.coordinator,
            collaborators=draft.collaborators,
            plan_time=draft.plan_time,
            status=draft.status or "未开始",
            key_achievement=draft.key_achievement,
            completion_standard=draft.completion_standard,
            source_type="大纲导入",
        )
        db.add(row)
        db.flush()
        crud.log(db, current_user, "大纲导入任务", "task", row.id, {}, crud.to_dict(row),
                 project_id=payload.project_id)
        created.append(crud.to_dict(row))
    db.commit()
    return created
