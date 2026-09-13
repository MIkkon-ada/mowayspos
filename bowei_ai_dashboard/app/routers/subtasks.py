import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import text

from .. import crud, models, schemas
from ..database import get_db
from ..domain import task_status as TS
from ..domain import project_lifecycle as PL
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
from ..compatibility.project_names import resolve_project_context
from ..services.project_close import require_project_business_writable
from ..services.key_task_execution import record_execution_event

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


def _submission_summary(row: models.UpdateSubmission, subtask_id: int) -> str:
    """Return the readable, key-task-scoped summary for a confirmed submission."""
    try:
        payload = json.loads(row.human_result_json or row.ai_result_json or "{}")
    except (TypeError, ValueError):
        payload = {}

    reports = payload.get("task_reports") if isinstance(payload, dict) else []
    if isinstance(reports, list):
        matched = next(
            (
                report for report in reports
                if isinstance(report, dict) and report.get("matched_subtask_id") == subtask_id
            ),
            None,
        )
        if matched:
            completed = matched.get("completed") or matched.get("completed_items")
            if isinstance(completed, list):
                completed = next((str(item).strip() for item in completed if str(item).strip()), "")
            if isinstance(completed, str) and completed.strip():
                return completed.strip()

    return (row.title or row.transcript_text or "").strip()[:160]


def _apply_work_progress_projection(rows: list[models.SubTask], payloads: list[dict], db: Session) -> None:
    """Attach latest confirmed progress and display-safe status facts without N+1 queries."""
    subtask_ids = [row.id for row in rows]
    latest_by_subtask: dict[int, dict] = {}
    latest_next_step_by_subtask: dict[int, str] = {}
    if subtask_ids:
        submissions = (
            db.query(models.UpdateSubmission)
            .filter(
                models.UpdateSubmission.related_subtask_id.in_(subtask_ids),
                models.UpdateSubmission.confirmed_at.is_not(None),
            )
            .order_by(
                models.UpdateSubmission.related_subtask_id.asc(),
                models.UpdateSubmission.confirmed_at.desc(),
                models.UpdateSubmission.id.desc(),
            )
            .all()
        )
        for submission in submissions:
            subtask_id = submission.related_subtask_id
            if subtask_id is None or subtask_id in latest_by_subtask:
                continue
            latest_by_subtask[subtask_id] = {
                "id": submission.id,
                "submitter": submission.submitter or "",
                "confirmed_at": submission.confirmed_at.isoformat(),
                "summary": _submission_summary(submission, subtask_id),
            }

        execution_events = (
            db.query(models.KeyTaskExecutionEvent)
            .filter(
                models.KeyTaskExecutionEvent.key_task_id.in_(subtask_ids),
                models.KeyTaskExecutionEvent.authority == "confirmed",
                models.KeyTaskExecutionEvent.affects_current_progress.is_(True),
            )
            .order_by(
                models.KeyTaskExecutionEvent.key_task_id.asc(),
                models.KeyTaskExecutionEvent.effective_at.desc(),
                models.KeyTaskExecutionEvent.id.desc(),
            )
            .all()
        )
        for event in execution_events:
            if event.key_task_id in latest_next_step_by_subtask:
                continue
            latest_next_step_by_subtask[event.key_task_id] = (event.next_step or "").strip()

    today = date.today()
    for row, payload in zip(rows, payloads):
        payload["latest_confirmed_submission"] = latest_by_subtask.get(row.id)
        payload["latest_next_step"] = latest_next_step_by_subtask.get(row.id, "")
        payload["is_overdue"] = bool(
            row.due_kind == "exact"
            and row.due_date is not None
            and row.due_date < today
            and TS.normalize(row.status) != TS.S_COMPLETED
        )
        payload["has_risk"] = bool((row.risk_note or "").strip())


def _validate_key_task_people(
    task: models.Task,
    assignee: str,
    collaborator_ids: list[int],
    db: Session,
) -> int | None:
    project_id = _get_task_project_id(task, db)
    if project_id is None:
        raise HTTPException(422, "关键任务必须属于有效项目")
    member_ids = {
        person_id
        for (person_id,) in db.query(models.ProjectMember.person_id)
        .filter(models.ProjectMember.project_id == project_id)
        .all()
    }
    collaborators = set(collaborator_ids or [])
    if not collaborators.issubset(member_ids):
        raise HTTPException(422, "协同人不属于当前项目")
    if collaborators:
        people_ids = {
            person_id
            for (person_id,) in db.query(models.Person.id)
            .filter(models.Person.id.in_(collaborators))
            .all()
        }
        if people_ids != collaborators:
            raise HTTPException(422, "协同人不存在")
    from ..services.notify import person_id_for_name as _pid_for_name
    assignee_id = _pid_for_name(assignee or "", db)
    if assignee_id is not None and assignee_id not in member_ids:
        raise HTTPException(422, "负责人不属于当前项目")
    if assignee_id is not None and assignee_id in collaborators:
        raise HTTPException(422, "负责人不能同时作为协同人")
    return assignee_id


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
    project_id = task.project_id
    if project_id is None:
        raise HTTPException(403, "permission denied")
    project = db.get(models.Project, project_id)
    require_project_business_writable(project_id, db)
    if project and not PL.is_execution_available(project.status):
        raise HTTPException(409, "当前项目阶段暂不能调整执行期关键任务")
    if context.get("is_tech_admin"):
        return
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


@router.get("/api/tasks/subtasks/batch")
def list_subtasks_batch(
    task_ids: str = "",
    deleted: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    return _list_subtasks_batch(task_ids, deleted, current_user, db)


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
    payloads = [crud.to_dict(row) for row in rows]
    _apply_work_progress_projection(rows, payloads, db)
    return payloads


def _list_subtasks_batch(
    task_ids: str = "",
    deleted: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """批量获取多个 task 的 subtask，一次请求替代多次 /api/tasks/{id}/subtasks。

    用途：工作推进表 plan 视图首屏渲染需要所有 task 的 subtask，避免 N+1 请求。
    权限：沿用单个接口策略——对每个 task 校验项目访问权；无权访问的 task 其结果不返回。
    返回：{ "1": [...], "2": [...] }，task_id 作为 key（字符串）。
    """
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    # 解析 task_ids，容错：空串/非法值/去重/上限
    raw_ids = [s.strip() for s in task_ids.split(",") if s.strip()]
    try:
        ids = list({int(s) for s in raw_ids})  # 去重
    except ValueError:
        raise HTTPException(400, "task_ids must be comma-separated integers")
    if not ids:
        return {}
    if len(ids) > 200:
        raise HTTPException(400, "too many task_ids (max 200)")
    tasks = db.query(models.Task).filter(models.Task.id.in_(ids)).all()
    result: dict[str, list] = {}
    visible_rows: list[models.SubTask] = []
    visible_payloads: list[dict] = []
    for task in tasks:
        if bool(getattr(task, "is_deleted", False)) and not deleted:
            continue
        project_id = _get_task_project_id(task, db)
        if project_id is not None:
            # 项目级权限校验：失败跳过该 task，不抛错打断整批
            try:
                require_project_access(current_user, project_id, db)
            except HTTPException:
                continue
        elif not (context.get("is_tech_admin") or context.get("is_ceo")):
            continue
        if deleted:
            try:
                _check_trash_access(context, task, db)
            except HTTPException:
                continue
        rows = (
            db.query(models.SubTask)
            .filter_by(task_id=task.id)
            .filter(models.SubTask.is_deleted.is_(bool(deleted)))
            .order_by(models.SubTask.created_at.asc())
            .all()
        )
        payloads = [crud.to_dict(row) for row in rows]
        result[str(task.id)] = payloads
        visible_rows.extend(rows)
        visible_payloads.extend(payloads)
    _apply_work_progress_projection(visible_rows, visible_payloads, db)
    return result


@router.get("/api/subtasks/{row_id}/detail")
def get_subtask_detail(
    row_id: int,
    project_id: int | None = None,
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
        resolved_project_id = _get_task_project_id(parent, db)
        if project_id is not None and resolved_project_id != project_id:
            raise HTTPException(404, "subtask not found")
        if resolved_project_id is not None:
            require_project_access(current_user, resolved_project_id, db)
        elif not (context.get("is_tech_admin") or context.get("is_ceo")):
            raise HTTPException(403, "permission denied")

    result = crud.to_dict(row)
    from .execution_schedules import to_schedule_dict
    schedules = db.query(models.ExecutionSchedule).filter(
        models.ExecutionSchedule.subtask_id == row.id,
        models.ExecutionSchedule.is_deleted.is_(False),
    ).order_by(models.ExecutionSchedule.start_date, models.ExecutionSchedule.due_date, models.ExecutionSchedule.id).all()
    result["execution_schedules"] = [to_schedule_dict(schedule) for schedule in schedules]

    # 执行详情使用：按关键任务聚合已确认/已提交的工作汇报，保留四项固定结构。
    import json as _json
    report_rows = (
        db.query(models.UpdateSubmission)
        .filter(models.UpdateSubmission.related_subtask_id == row.id)
        .order_by(models.UpdateSubmission.created_at.desc())
        .limit(50)
        .all()
    )
    result["work_reports"] = []
    for report_row in report_rows:
        try:
            payload = _json.loads(report_row.human_result_json or report_row.ai_result_json or "{}")
        except Exception:
            payload = {}
        task_reports = payload.get("task_reports") or []
        matched = next((item for item in task_reports if item.get("matched_subtask_id") == row.id), None)
        if not matched:
            matched = payload if any(key in payload for key in ("completed_items", "next_steps", "issues", "achievements")) else {}
        completed = matched.get("completed") or matched.get("completed_items") or []
        if isinstance(completed, str):
            completed = [completed]
        result["work_reports"].append({
            "id": report_row.id,
            "submitter": report_row.submitter,
            "created_at": report_row.created_at.isoformat() if report_row.created_at else None,
            "completed_items": completed if isinstance(completed, list) else [],
            "next_steps": matched.get("next_steps") or [],
            "issues": matched.get("subtask_issues") or matched.get("issues") or [],
            "achievements": matched.get("achievements") or [],
        })

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
        .filter(models.Achievement.related_subtask_id == row.id)
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
        .filter(models.Issue.related_subtask_id == row.id)
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
    require_project_business_writable(_get_task_project_id(task, db), db)

    data = payload.model_dump()
    assignee_id = _validate_key_task_people(task, payload.assignee, payload.collaborator_ids, db)
    if (data.get("assignee") or "").strip() and TS.normalize(data.get("status", "")) == TS.S_NOT_STARTED:
        data["status"] = TS.S_IN_PROGRESS

    parent_was_completed = TS.normalize(task.status) == TS.S_COMPLETED

    row = models.SubTask(task_id=task_id, **data)
    row.assignee_id = assignee_id
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
    require_project_business_writable(_get_task_project_id(task, db), db)

    before = crud.to_dict(row)
    assignee_id = _validate_key_task_people(task, payload.assignee, payload.collaborator_ids, db)
    before_assignee = (row.assignee or "").strip()
    crud.update_model(row, payload.model_dump())
    row.assignee_id = assignee_id

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
    require_project_business_writable(_get_task_project_id(task, db), db)

    before_status = row.status or ""
    row.status = payload.status
    row.edit_count = (row.edit_count or 0) + 1
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
    # A deliberate Key Task status change is an authoritative business fact.  It
    # is projected to the execution timeline, but does not replace the source
    # object: SubTask remains the source of truth for the status itself.
    if TS.normalize(before_status) != TS.normalize(payload.status):
        record_execution_event(
            db,
            project_id=project_id,
            key_task_id=row.id,
            event_type="key_task_status_changed",
            source_type="key_task",
            source_id=row.id,
            dedupe_key=f"key-task:{row.id}:status:{row.edit_count}:{TS.normalize(payload.status)}",
            actor_name_snapshot=current_user,
            occurred_at=utc_now(),
            confirmed_at=utc_now(),
            effective_at=utc_now(),
            affects_current_progress=True,
            status_before=before_status,
            status_after=payload.status,
            progress_summary=f"关键任务状态更新为{payload.status}",
            authority="confirmed",
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
    require_project_business_writable(_get_task_project_id(task, db), db)
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
    require_project_business_writable(_get_task_project_id(task, db), db)
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
