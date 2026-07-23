from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import issue_type as IT
from ..domain import issue_flow as IF
from ..domain import source_type as ST
from ..permissions import (
    PROJECT_ROLE_COORD_KEY,
    PROJECT_ROLE_COORDINATOR,
    PROJECT_ROLE_OWNER_KEY,
    PROJECT_ROLE_OWNER,
    can_view_issue_decisions,
    can_view_issue_risks,
    can_view_project,
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_owner_or_admin,
    require_project_role,
    is_project_member,
)
from ..time_utils import utc_now

from ..services.notify import person_id_for_name as _pid_for_name
from ..services.project_resolution import resolve_project_context
from ..services.project_close import require_project_business_writable

router = APIRouter(prefix="/api/issues", tags=["issues"])
_CLOSED_STATUSES = {"已关闭", "已决策", "已解决", "关闭"}

def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _issue_write_project_id(row: models.Issue, context: dict, db: Session) -> int | None:
    project_id = resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]
    if project_id is not None:
        return project_id
    if context.get("is_tech_admin"):
        return None
    raise HTTPException(403, "permission denied")


def _row_project_id(row: models.Issue, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]


def _row_project_name(row: models.Issue, db: Session) -> str:
    resolved = resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )
    return resolved["project_name"] or row.special_project or ""


_ISSUE_STORAGE_LABELS: dict[str, str] = {
    IT.TYPE_ISSUE: IF.TYPE_ISSUE,
    IT.TYPE_RISK: IF.TYPE_RISK,
    IT.TYPE_COORDINATION: IF.TYPE_COORDINATE,
    IT.TYPE_DECISION: IF.TYPE_DECISION,
    IT.TYPE_UNKNOWN: IF.TYPE_ISSUE,
}


def _storage_issue_type(issue_type: str | None) -> str:
    return _ISSUE_STORAGE_LABELS.get(IT.normalize(issue_type), IF.TYPE_ISSUE)


def _issue_type_matches_filter(row: models.Issue, issue_type: str) -> bool:
    normalized_filter_type = IT.normalize(issue_type)
    row_type = IT.normalize(row.issue_type)
    if normalized_filter_type == IT.TYPE_DECISION:
        return _is_decision_issue(row)
    if normalized_filter_type == IT.TYPE_ISSUE:
        return row_type == IT.TYPE_ISSUE and not _is_decision_issue(row)
    return row_type == normalized_filter_type


# ── 角色可见范围辅助 ──────────────────────────────────────────

def _can_view_project_all_issues(context: dict, project_id: int, db: Session) -> bool:
    """检查当前用户是否有项目全部问题的可见权限。"""
    if context.get("is_tech_admin") or context.get("is_ceo"):
        return True
    person_id = context.get("person_id")
    if person_id is None:
        return False
    roles = get_all_project_roles(int(person_id), int(project_id), db)
    if roles:
        return any(r in ("owner", "coordinator", "project_ceo") for r in roles)
    # Fallback: 如果 project_members 无数据，从旧 context 推导
    proj_name = _get_project_name(project_id, db)
    if proj_name:
        if proj_name in context.get("owned_projects", []):
            return True
        if proj_name in context.get("coordinated_projects", []):
            return True
        if proj_name in context.get("ceo_projects", []):
            return True
    return False


def _get_project_name(project_id: int, db: Session) -> str | None:
    """从 projects 表按 id 查名称。"""
    try:
        row = db.execute(
            text("SELECT name FROM projects WHERE id = :id"),
            {"id": project_id},
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _is_issue_related_to_user(row: models.Issue, username: str, person_name: str) -> bool:
    """普通成员是否与该问题相关（reporter / owner / helper）。"""
    return (
        (row.reporter or "") == username
        or (row.owner or "") == username
        or (row.helper or "") == username
        or bool(person_name) and (row.owner or "") == person_name
        or bool(person_name) and (row.helper or "") == person_name
    )


# ── 业务辅助 ──────────────────────────────────────────────────

def _is_decision_issue(row: models.Issue) -> bool:
    need_decision_by = (row.need_decision_by or "").strip()
    return IT.is_decision(row.issue_type) or bool(need_decision_by)


def _can_view_issue_row(context: dict, row: models.Issue, db: Session) -> bool:
    if not can_view_project(context, _row_project_name(row, db)):
        return False
    if not _is_decision_issue(row):
        return can_view_issue_risks(context)
    # Decision-type issue:
    # Global access (CEO / tech_admin)
    if can_view_issue_decisions(context):
        return True
    # Project owner sees ALL issue types in their own project
    proj_name = _row_project_name(row, db).strip()
    return bool(proj_name) and proj_name in context.get("owned_projects", [])


def _sync_issue_closed_at(row: models.Issue) -> None:
    if (row.status or "").strip() in _CLOSED_STATUSES:
        row.closed_at = row.closed_at or utc_now()
    else:
        row.closed_at = None


# ── 端点 ──────────────────────────────────────────────────────

@router.get("")
def list_issues(
    project_id: int | None = None,
    issue_type: str | None = None,
    special_project: str | None = None,
    owner: str | None = None,
    priority: str | None = None,
    status: str | None = None,
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

    q = db.query(models.Issue).order_by(models.Issue.updated_at.desc())
    if effective_project_id is not None:
        q = q.filter(models.Issue.project_id == effective_project_id)
        # 普通成员只看自己相关的问题
        if not _can_view_project_all_issues(context, effective_project_id, db):
            current_person_name = context.get("name") or ""
            q = q.filter(
                or_(
                    models.Issue.reporter == current_user,
                    models.Issue.owner == current_user,
                    models.Issue.helper == current_user,
                    models.Issue.owner == current_person_name,
                    models.Issue.helper == current_person_name,
                )
            )

    result = []
    for row in q.limit(500).all():
        if issue_type:
            if not _issue_type_matches_filter(row, issue_type):
                continue
        if owner and row.owner != owner:
            continue
        if priority and row.priority != priority:
            continue
        if status and row.status != status:
            continue
        result.append(crud.to_dict(row))
    return result


@router.post("")
def create_issue(
    payload: schemas.IssuePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    project_id = payload.project_id
    if project_id is None:
        raise HTTPException(422, "project_id is required")
    require_project_access(current_user, project_id, db)
    require_project_business_writable(project_id, db)

    normalized_type = IT.normalize(payload.issue_type)
    if normalized_type == IT.TYPE_DECISION and not can_view_issue_decisions(context):
        raise HTTPException(403, "permission denied")

    crud.validate_subtask_link(db, project_id, payload.related_task_id, payload.related_subtask_id)

    data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    row = models.Issue(**data)
    row.issue_type = _storage_issue_type(normalized_type)
    row.source_type = ST.normalize(payload.source_type or "人工录入")
    # Derive status: normalize explicit value, then apply type-specific default
    # when status is still the generic "待处理" (schema default or explicit).
    normalized_status = IF.normalize_status(payload.status)
    if normalized_status == IF.STATUS_PENDING:
        normalized_status = IF.STATUS_PENDING_DECISION if IT.is_decision(normalized_type) else IF.STATUS_PENDING
    row.status = normalized_status
    row.project_id = project_id
    row.owner_id = _pid_for_name(row.owner or "", db)
    if not row.special_project:
        row.special_project = resolve_project_context(
            db,
            project_id=project_id,
            special_project=payload.special_project,
        )["project_name"] or payload.special_project or ""
    _sync_issue_closed_at(row)
    row.reporter = current_user
    db.add(row)
    db.flush()
    crud.log(db, current_user, "issue_create", "issue", row.id, {}, crud.to_dict(row))

    # 通知项目负责人/统筹人
    from ..services.notify import send as _notify, person_name_for_account, person_id_for_account, project_owner_ids
    caller_name = person_name_for_account(current_user, db)
    caller_id = person_id_for_account(current_user, db)
    for owner_id in project_owner_ids(project_id, db):
        if owner_id != caller_id:
            _notify(
                db,
                recipient_id=owner_id,
                ntype="issue_reported",
                title=f"有新问题上报：{row.description[:40]}{'…' if len(row.description) > 40 else ''}",
                body=f"上报人：{caller_name}，类型：{row.issue_type}，优先级：{row.priority}",
                link=f"/project/{project_id}/issues",
                project_id=project_id,
            )

    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


@router.get("/mine")
def list_my_issues(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """返回当前用户自己上报的问题（不受角色权限限制，reporter 可见自己的）。"""
    rows = (
        db.query(models.Issue)
        .filter(models.Issue.reporter == current_user)
        .order_by(models.Issue.updated_at.desc())
        .limit(200)
        .all()
    )
    return [crud.to_dict(r) for r in rows]


@router.get("/{row_id}")
def get_issue(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _row_project_id(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
        # N4-P2-L: 普通成员只能看与自己相关的问题
        if not _can_view_project_all_issues(context, project_id, db):
            current_person_name = context.get("name") or ""
            if not _is_issue_related_to_user(row, current_user, current_person_name):
                raise HTTPException(403, "permission denied")
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return crud.to_dict(row)


@router.put("/{row_id}")
def update_issue(
    row_id: int,
    payload: schemas.IssuePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
        if row.reporter != current_user:
            require_project_role(
                current_user,
                project_id,
                [PROJECT_ROLE_OWNER_KEY],
                db,
            )
    elif not context.get("is_tech_admin") and row.reporter != current_user:
        raise HTTPException(403, "permission denied")

    require_project_business_writable(project_id, db)

    crud.validate_subtask_link(db, project_id, payload.related_task_id if payload.related_task_id is not None else row.related_task_id, payload.related_subtask_id)

    before = crud.to_dict(row)
    update_data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    if "issue_type" in update_data and update_data["issue_type"]:
        update_data["issue_type"] = _storage_issue_type(update_data["issue_type"])
    if "status" in update_data and update_data["status"]:
        update_data["status"] = IF.normalize_status(update_data["status"])
    if "source_type" in update_data:
        update_data["source_type"] = ST.normalize(update_data["source_type"] or "人工录入")
    crud.update_model(row, update_data)
    row.owner_id = _pid_for_name(row.owner or "", db)
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "issue_update", "issue", row.id, before, payload.model_dump(), project_id=project_id)
    db.commit()
    return crud.to_dict(row)


@router.delete("/{row_id}")
def delete_issue(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_owner_or_admin(current_user, project_id, db)

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    crud.log(db, current_user, "issue_delete", "issue", row_id, before, {})
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.patch("/{row_id}/status")
def patch_status(
    row_id: int,
    payload: schemas.StatusRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )
    require_project_business_writable(project_id, db)

    before_status = row.status
    row.status = IF.normalize_status(payload.status)
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "issue_update_status", "issue", row.id,
             {"status": before_status}, {"status": payload.status},
             project_id=project_id)
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/resolve")
def resolve_issue(
    row_id: int,
    payload: schemas.ResolveRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )
    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    row.status = IF.STATUS_RESOLVED
    if payload.resolution:
        row.resolution = payload.resolution
    if payload.handler_reply:
        row.handler_reply = payload.handler_reply
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "issue_resolve", "issue", row.id, before, crud.to_dict(row), project_id=project_id)

    # 如果来自 AI 确认中心，回写任务卡意见
    if row.source_type == "ai_confirmation" and row.source_submission_id is not None:
        try:
            from ..services import escalation as ESC
            ESC.write_back_to_card(db, row)
            db.flush()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("write_back_to_card failed for issue %s: %s", row.id, e)
    if (row.reporter or "").strip() and row.reporter != current_user:
        from ..services.notify import send as _notify, person_id_for_account
        reply_text = payload.handler_reply or payload.resolution or "无"
        _notify(db, recipient_id=person_id_for_account(row.reporter, db),
                recipient=row.reporter, ntype="issue_resolved",
                title=f"你上报的问题已解决：{row.description[:40]}",
                body=f"负责人回复：{reply_text}",
                link=f"/home/mytasks",
                project_id=project_id)
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/close")
def close_issue(
    row_id: int,
    payload: schemas.CloseRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_owner_or_admin(current_user, project_id, db)
    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    row.status = IF.STATUS_CLOSED
    if payload.reason:
        row.resolution = payload.reason
    if payload.handler_reply:
        row.handler_reply = payload.handler_reply
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "issue_close", "issue", row.id, before, crud.to_dict(row), project_id=project_id)
    if (row.reporter or "").strip() and row.reporter != current_user:
        from ..services.notify import send as _notify, person_id_for_account
        reply_text = payload.handler_reply or payload.reason or "无"
        _notify(db, recipient_id=person_id_for_account(row.reporter, db),
                recipient=row.reporter, ntype="issue_closed",
                title=f"你上报的问题已关闭：{row.description[:40]}",
                body=f"负责人回复：{reply_text}",
                link=f"/home/mytasks",
                project_id=project_id)
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/assign-helper")
def assign_helper(
    row_id: int,
    payload: schemas.AssignHelperRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )
    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    row.helper = payload.helper
    # N4-P2-M: 指定协助人后自动进入“待协调”
    if (payload.helper or "").strip():
        row.status = IF.STATUS_COORDINATING
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "issue_assign_helper", "issue", row.id, before,
             {"helper": payload.helper, "status": row.status}, project_id=project_id)
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/request-ceo")
def request_ceo(
    row_id: int,
    payload: schemas.RequestCeoRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")
    project_id = _issue_write_project_id(row, context, db)
    if project_id is not None:
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY],
            db,
        )
    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    row.issue_type = _storage_issue_type(IT.TYPE_DECISION)
    row.status = IF.STATUS_PENDING_DECISION
    row.need_decision_by = payload.need_decision_by
    if payload.note:
        existing = (row.resolution or "").strip()
        row.resolution = (existing + "\n" + payload.note).strip() if existing else payload.note
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "issue_escalate_to_coach", "issue", row.id, before, crud.to_dict(row), project_id=project_id)
    from ..services.notify import send as _notify, person_name_for_account, person_id_for_account, project_coach_person_ids
    caller_name = person_name_for_account(current_user, db)
    caller_id = person_id_for_account(current_user, db)
    for coach_id in project_coach_person_ids(project_id, db):
        if coach_id != caller_id:
            _notify(db, recipient_id=coach_id, ntype="issue_needs_decision",
                    title=f"有问题需要您决策：{row.description[:40]}{'…' if len(row.description) > 40 else ''}",
                    body=f"上报人：{caller_name}，决策人：{payload.need_decision_by or '待定'}，专项：{row.special_project or ''}",
                    link=f"/project/{project_id}/issues" if project_id else "",
                    project_id=project_id)
    db.commit()
    return crud.to_dict(row)


# ── 任务卡问题流转：统筹/教练提交意见 + 负责人确认 ──────────────


class SubmitOpinionRequest(BaseModel):
    opinion: str


@router.patch("/{row_id}/submit-opinion")
def submit_opinion(
    row_id: int,
    payload: SubmitOpinionRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """统筹/教练提交意见，Issue 进入「待负责人确认」状态。"""
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")

    # 权限：统筹/教练或超管可操作
    project_id = row.project_id
    if not context.get("is_tech_admin"):
        can_opinion = False
        if project_id is not None:
            roles = set(get_all_project_roles(current_user, project_id, db))
            # 统筹人 对 待协调 的 Issue 可提交意见
            if PROJECT_ROLE_COORD_KEY in roles and row.issue_type == IT.TYPE_COORDINATE:
                can_opinion = True
            # 项目企业教练(project_ceo) 对 需决策 的 Issue 可提交意见
            if "project_ceo" in roles and row.issue_type == IT.TYPE_DECISION:
                can_opinion = True
        if not can_opinion:
            raise HTTPException(403, "permission denied — 仅该专项的统筹人/企业教练可提交意见")

    opinion = (payload.opinion or "").strip()
    if not opinion:
        raise HTTPException(400, "请填写意见")

    # 状态校验：只能在 待协调/待决策 状态提交意见
    if row.status not in {IF.STATUS_COORDINATING, IF.STATUS_PENDING_DECISION, IF.STATUS_IN_PROGRESS}:
        raise HTTPException(409, f"当前状态「{row.status}」不能提交意见")

    before = crud.to_dict(row)
    row.opinion = opinion
    row.status = IF.STATUS_PENDING_OWNER_CONFIRM
    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "issue_submit_opinion", "issue", row.id, before, crud.to_dict(row), project_id=project_id)

    # 通知负责人
    if row.owner and row.owner != current_user:
        from ..services.notify import send as _notify, person_id_for_account
        _notify(
            db, recipient_id=person_id_for_account(row.owner, db),
            recipient=row.owner, ntype="issue_opinion_submitted",
            title=f"统筹/教练已提交意见，请确认：{row.description[:40]}",
            body=f"意见：{opinion}",
            link=f"/work/issues?projectId={project_id}&issueId={row.id}" if project_id else "",
            project_id=project_id,
        )

    db.commit()
    return crud.to_dict(row)


class OwnerConfirmOpinionRequest(BaseModel):
    accepted: bool = True
    note: str = ""


@router.patch("/{row_id}/owner-confirm")
def owner_confirm_opinion(
    row_id: int,
    payload: OwnerConfirmOpinionRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """负责人确认意见：accepted=true → 已解决并回写；accepted=false → 退回继续处理。"""
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Issue, row_id)
    if not row:
        raise HTTPException(404, "issue not found")

    # 权限：Issue owner 或超管
    if not context.get("is_tech_admin"):
        if row.owner != current_user:
            project_id = row.project_id
            if project_id is not None:
                require_project_role(current_user, project_id, [PROJECT_ROLE_OWNER_KEY], db)
            else:
                raise HTTPException(403, "permission denied — 仅负责人可确认")

    # 状态校验
    if row.status != IF.STATUS_PENDING_OWNER_CONFIRM:
        raise HTTPException(409, f"当前状态「{row.status}」不能确认意见")

    before = crud.to_dict(row)
    project_id = row.project_id

    if payload.accepted:
        # 确认接受 → 已解决，回写任务卡
        row.status = IF.STATUS_RESOLVED
        resolution_parts = [row.opinion or ""]
        if payload.note:
            resolution_parts.append(f"负责人确认：{payload.note}")
        row.resolution = "\n".join(p for p in resolution_parts if p)
        _sync_issue_closed_at(row)
        row.edit_count = (row.edit_count or 0) + 1
        crud.log(db, current_user, "issue_owner_accept_opinion", "issue", row.id, before, crud.to_dict(row), project_id=project_id)

        # 回写任务卡
        if row.source_type == "ai_confirmation" and row.source_submission_id is not None:
            try:
                from ..services import escalation as ESC
                ESC.write_back_to_card(db, row)
                db.flush()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error("write_back_to_card failed for issue %s: %s", row.id, e)
    else:
        # 拒绝接受 → 退回处理中，等统筹/教练补充
        row.status = IF.STATUS_IN_PROGRESS
        if payload.note:
            row.resolution = f"负责人要求补充：{payload.note}"
        row.edit_count = (row.edit_count or 0) + 1
        crud.log(db, current_user, "issue_owner_reject_opinion", "issue", row.id, before, crud.to_dict(row), project_id=project_id)

        # 通知统筹/教练补充
        from ..services.notify import send as _notify, person_id_for_account
        from ..services.notify import project_coach_person_ids, project_coordinator_ids
        if project_id is not None:
            if row.issue_type == IT.TYPE_DECISION:
                rids = project_coach_person_ids(project_id, db)
            else:
                rids = project_coordinator_ids(project_id, db)
            caller_id = person_id_for_account(current_user, db)
            for rid in rids:
                if rid != caller_id:
                    _notify(
                        db, recipient_id=rid, ntype="issue_opinion_rejected",
                        title=f"负责人要求补充意见：{row.description[:40]}",
                        body=f"负责人反馈：{payload.note or '无'}",
                        link=f"/work/issues?projectId={project_id}&issueId={row.id}",
                        project_id=project_id,
                    )

    db.commit()
    return crud.to_dict(row)
