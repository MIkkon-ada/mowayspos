import asyncio
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import submission_status as SS
from sqlalchemy import or_ as sql_or

from ..permissions import (
    PROJECT_ROLE_COORDINATOR,
    PROJECT_ROLE_OWNER,
    PROJECT_ROLE_OWNER_KEY,
    ROLE_CEO,
    can_view_project,
    can_view_submission,
    get_all_project_roles,
    get_current_user_name,
    get_person_id,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_role,
)
from ..time_utils import utc_now
from ..services.policy import can_submit_to_project as _can_submit_to_project
from ..services.extractor import extract_update
from ..services.notify import person_id_for_account as _pid_for_account, send as _notify
from ..services.project_resolution import resolve_project_context
from ..archived_guard import require_project_not_archived

router = APIRouter(prefix="/api/updates", tags=["updates"])


# ── 内部工具 ───────────────────────────────────────────────────

def _update_human_result(row: models.UpdateSubmission) -> dict:
    try:
        return json.loads(row.human_result_json or row.ai_result_json or "{}")
    except Exception:
        return {}


def _can_view_update(context: dict, row: models.UpdateSubmission) -> bool:
    human = _update_human_result(row)
    return can_view_submission(context, human, row.submitter or "")


def _project_owner_person_ids(project_id: int, db: Session) -> list[int]:
    rows = (
        db.query(models.ProjectMember.person_id)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.role.in_([PROJECT_ROLE_OWNER, "owner"]),
        )
        .all()
    )
    seen: set[int] = set()
    result: list[int] = []
    for (person_id,) in rows:
        if person_id and person_id not in seen:
            seen.add(person_id)
            result.append(person_id)
    return result


def _notify_project_owners_of_submission(
    db: Session,
    *,
    project_id: int,
    submitter: str,
    submitter_id: int | None,
) -> None:
    for owner_id in _project_owner_person_ids(project_id, db):
        if submitter_id and owner_id == submitter_id:
            continue
        _notify(
            db,
            recipient_id=owner_id,
            ntype="submission_pending",
            title="有新的提交待确认",
            body=f"{submitter} 提交了一条更新，请前往 AI 确认中心处理。",
            link=f"/project/{project_id}/confirm",
            project_id=project_id,
        )


def _ceo_name(db: Session) -> str:
    row = db.query(models.Person).filter_by(system_role=ROLE_CEO, is_active=True).first()
    return row.name if row else ""


def _require_project_active(project_id: int | None, db: Session) -> None:
    """仅 active 项目允许提交工作汇报和获取可汇报上下文。

    与 require_project_not_archived 互补：
    - archived_guard 拦截归档项目（status == archived）。
    - 本函数拦截所有非 active 状态（draft / dispatched / pending_review / returned / archived）。
    """
    if project_id is None:
        return
    proj = db.get(models.Project, project_id)
    if proj is None:
        return
    status = (getattr(proj, "status", "") or "").strip()
    lifecycle = (getattr(proj, "lifecycle_status", "") or "").strip()
    if status == "active" or lifecycle == "active":
        return
    raise HTTPException(409, "项目尚未启动，暂不能提交工作汇报。")


# ── 端点 ───────────────────────────────────────────────────────

@router.get("/voice-context")
def get_voice_context(
    project_id: int | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """
    获取用户可用于汇报的子任务上下文。
    - 传 project_id：返回该项目的子任务（需项目访问权限）
    - 不传 project_id：返回用户所有可访问项目的子任务（跨项目汇报）
    """
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    display_name: str = context.get("name") or current_user

    if project_id is not None:
        require_project_access(current_user, project_id, db)
        proj = db.get(models.Project, project_id)
        if not proj:
            raise HTTPException(404, "project not found")
        _require_project_active(project_id, db)

    person_id = context.get("person_id")
    is_project_manager = False
    user_project_role: str | None = None

    if context.get("can_view_all"):
        is_project_manager = True
        user_project_role = "owner"
    elif project_id is not None:
        member_roles = get_all_project_roles(person_id, project_id, db) if person_id else []
        if member_roles:
            if "owner" in member_roles:
                is_project_manager = True
                user_project_role = "owner"
            elif "coordinator" in member_roles:
                is_project_manager = True
                user_project_role = "coordinator"

    # 非管理员只能看到自己负责/协助的子任务
    active_proj_ids = db.query(models.Project.id).filter(models.Project.status != "archived")
    q = (
        db.query(models.SubTask, models.Task)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
            models.SubTask.status.notin_(["已完成", "已关闭"]),
            models.Task.project_id.in_(active_proj_ids),
        )
    )

    if project_id is not None:
        q = q.filter(models.Task.project_id == project_id)

    if not is_project_manager:
        q = q.filter(
            sql_or(
                models.SubTask.assignee == display_name,
                models.Task.owner == display_name,
            )
        )

    rows = q.order_by(models.Task.id.asc(), models.SubTask.created_at.asc()).all()

    result = []
    for subtask, task in rows:
        if is_project_manager:
            relation = user_project_role or "coordinator"
        elif task.owner == display_name:
            relation = "task_owner"
        else:
            relation = "subtask_assignee"

        d = crud.to_dict(subtask)
        d["parent_key_task"] = task.key_task or ""
        d["parent_task_id"] = task.id
        d["parent_project_id"] = task.project_id
        d["user_relation"] = relation
        result.append(d)

    return result


@router.post("/extract")
async def extract(
    payload: schemas.ExtractRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """AI draft extraction only; no canonical write."""
    current_user = require_login(current_user, db)
    if payload.project_id is not None:
        require_project_access(current_user, payload.project_id, db)
    user_subtasks = [s.model_dump() for s in payload.user_subtasks] if payload.user_subtasks else None
    ceo_name = _ceo_name(db)
    try:
        result = await asyncio.to_thread(
            extract_update,
            payload.source_type,
            payload.transcript_text,
            payload.submitter,
            payload.llm_provider,
            ceo_name,
            require_llm=True,
            user_subtasks=user_subtasks,
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    return {"suggestion": result}


@router.post("")
async def create_update(
    payload: schemas.ExtractRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    submitter = payload.submitter or current_user
    project_id = payload.project_id

    if not context.get("person_id"):
        context = dict(context, person_id=get_person_id(current_user, db))

    # project_id 可选：未传时从 human_result 的 task_reports 反查
    human_result = payload.human_result or payload.edited_suggestion
    if project_id is None and human_result:
        # 策略1：从 special_project 名称反查
        ai_project_name = (human_result or {}).get("special_project", "")
        if ai_project_name:
            resolved = resolve_project_context(db, special_project=ai_project_name)
            project_id = resolved["project_id"]
        # 策略2：从 task_reports 的 parent_task_id 反查
        if project_id is None:
            task_reports = (human_result or {}).get("task_reports") or []
            for report in task_reports:
                if isinstance(report, dict):
                    ptid = report.get("parent_task_id")
                    if ptid:
                        parent_task = db.get(models.Task, int(ptid))
                        if parent_task and parent_task.project_id:
                            project_id = parent_task.project_id
                            break

    if project_id is None:
        raise HTTPException(422, "AI 未能识别所属项目，请手动选择项目或在汇报中提及项目名称")

    if not _can_submit_to_project(context, project_id, db):
        raise HTTPException(403, "permission denied")
    require_project_not_archived(project_id, db)
    _require_project_active(project_id, db)

    # 收集所有卡片涉及的项目 ID，用于跨项目通知和归档检查
    card_project_ids: set[int] = {project_id}
    if human_result:
        for report in ((human_result or {}).get("task_reports") or []):
            if isinstance(report, dict):
                ptid = report.get("parent_task_id")
                if ptid:
                    parent_task = db.get(models.Task, int(ptid))
                    if parent_task and parent_task.project_id:
                        card_project_ids.add(parent_task.project_id)
    # 对每个卡片项目检查归档
    for pid in card_project_ids:
        require_project_not_archived(pid, db)

    cutoff = utc_now() - timedelta(seconds=60)
    dup = db.query(models.UpdateSubmission).filter(
        models.UpdateSubmission.submitter == (submitter or ""),
        models.UpdateSubmission.transcript_text == (payload.transcript_text or ""),
        models.UpdateSubmission.source_type == (payload.source_type or ""),
        models.UpdateSubmission.created_at >= cutoff,
    ).first()
    if dup:
        dup_provider = json.loads(dup.ai_result_json or "{}").get("engine", "rules")
        current_provider = payload.llm_provider or "rules"
        if dup_provider == current_provider:
            return {"submission": crud.to_dict(dup), "suggestion": json.loads(dup.ai_result_json or "{}")}

    if payload.human_result or payload.edited_suggestion:
        result = dict(payload.human_result or payload.edited_suggestion)
    else:
        ceo_name = _ceo_name(db)
        result = await asyncio.to_thread(
            extract_update,
            payload.source_type,
            payload.transcript_text,
            submitter,
            None,
            ceo_name,
            require_llm=False,
        )
    human_result = payload.human_result or payload.edited_suggestion or result

    proj_name = resolve_project_context(
        db,
        project_id=project_id,
        special_project=payload.special_project,
    )["project_name"] or ""
    if proj_name:
        human_result = dict(human_result)
        if not human_result.get("special_project"):
            human_result["special_project"] = proj_name

    submitter_id = _pid_for_account(current_user, db) or context.get("person_id") or get_person_id(submitter, db)
    row = models.UpdateSubmission(
        project_id=project_id,
        source_type=payload.source_type,
        submitter=submitter or "",
        submitter_id=submitter_id,
        title=payload.title or "工作汇报",
        transcript_text=payload.transcript_text,
        ai_result_json=json.dumps(result, ensure_ascii=False),
        human_result_json=json.dumps(human_result, ensure_ascii=False),
        confirm_status=SS.S_NEW,
        confidence=human_result.get("confidence", result.get("confidence", 0)),
    )
    db.add(row)
    # 通知所有卡片涉及项目的负责人（支持跨项目提交）
    for pid in card_project_ids:
        _notify_project_owners_of_submission(
            db,
            project_id=pid,
            submitter=submitter or current_user,
            submitter_id=submitter_id,
        )
    db.commit()
    db.refresh(row)
    return {"submission": crud.to_dict(row), "suggestion": result}


@router.get("")
def list_updates(
    project_id: int | None = None,
    special_project: str | None = None,
    mine: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)

    if mine:
        rows = db.query(models.UpdateSubmission).filter(
            models.UpdateSubmission.submitter == current_user
        ).order_by(models.UpdateSubmission.created_at.desc()).all()
        result = []
        for row in rows:
            item = crud.to_dict(row)
            human = _update_human_result(row)
            item["special_project"] = (
                human.get("special_project")
                or (human.get("task") or {}).get("special_project")
                or ""
            )
            result.append(item)
        return result

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
        if not (context.get("is_tech_admin") or context.get("is_ceo")):
            raise HTTPException(403, "permission denied")

    rows = db.query(models.UpdateSubmission).order_by(
        models.UpdateSubmission.created_at.desc()
    ).limit(500).all()

    result = []
    for row in rows:
        if effective_project_id is not None:
            row_ctx = resolve_project_context(
                db,
                project_id=row.project_id,
                json_payload=_update_human_result(row),
            )
            if row_ctx["project_id"] != effective_project_id:
                continue
        item = crud.to_dict(row)
        human = _update_human_result(row)
        item["special_project"] = (
            human.get("special_project")
            or (human.get("task") or {}).get("special_project")
            or ""
        )
        result.append(item)
    return result


@router.get("/{submission_id}")
def get_update(
    submission_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.UpdateSubmission, submission_id)
    if not row:
        raise HTTPException(404, "update not found")
    human = _update_human_result(row)
    project_ctx = resolve_project_context(
        db,
        project_id=row.project_id,
        json_payload=human,
    )
    project_id = project_ctx["project_id"]
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    data = crud.to_dict(row)
    data["ai_result"] = json.loads(row.ai_result_json or "{}")
    data["human_result"] = json.loads(row.human_result_json or row.ai_result_json or "{}")
    return data


@router.delete("/{submission_id}")
def delete_update(
    submission_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.UpdateSubmission, submission_id)
    if not row:
        raise HTTPException(404, "update not found")

    project_id = row.project_id
    if project_id is None:
        if not context.get("is_tech_admin"):
            raise HTTPException(403, "permission denied")
    else:
        if row.submitter == current_user:
            pass
        elif context.get("is_tech_admin"):
            pass
        else:
            require_project_role(current_user, project_id, [PROJECT_ROLE_OWNER_KEY], db)

    require_project_not_archived(project_id, db)
    db.delete(row)
    db.commit()
    return {"ok": True}
