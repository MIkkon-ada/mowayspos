from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import issue_flow as IF
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
)
from ..time_utils import utc_now

from ..services.notify import person_id_for_name as _pid_for_name
from ..services.project_resolution import resolve_project_context
from ..archived_guard import require_project_not_archived

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


# ── 业务辅助 ──────────────────────────────────────────────────

def _is_decision_issue(row: models.Issue) -> bool:
    need_decision_by = (row.need_decision_by or "").strip()
    return IF.normalize_type(row.issue_type) == IF.TYPE_DECISION or bool(need_decision_by)


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

    result = []
    for row in q.limit(500).all():
        if issue_type:
            normalized_filter_type = IF.normalize_type(issue_type)
            if normalized_filter_type == IF.TYPE_DECISION:
                if not _is_decision_issue(row):
                    continue
            elif issue_type == "problem":
                if _is_decision_issue(row):
                    continue
            elif IF.normalize_type(row.issue_type) != normalized_filter_type:
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
    require_project_not_archived(project_id, db)

    normalized_type = IF.normalize_type(payload.issue_type)
    if normalized_type == IF.TYPE_DECISION and not can_view_issue_decisions(context):
        raise HTTPException(403, "permission denied")

    data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    row = models.Issue(**data)
    row.issue_type = normalized_type
    # Derive status: normalize explicit value, then apply type-specific default
    # when status is still the generic "待处理" (schema default or explicit).
    normalized_status = IF.normalize_status(payload.status)
    if normalized_status == IF.STATUS_PENDING:
        normalized_status = IF.default_status_for_type(normalized_type)
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
    crud.log(db, current_user, "新建问题", "issue", row.id, {}, crud.to_dict(row))

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

    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    update_data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}
    if "issue_type" in update_data and update_data["issue_type"]:
        update_data["issue_type"] = IF.normalize_type(update_data["issue_type"])
    if "status" in update_data and update_data["status"]:
        update_data["status"] = IF.normalize_status(update_data["status"])
    crud.update_model(row, update_data)
    row.owner_id = _pid_for_name(row.owner or "", db)
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "修改问题", "issue", row.id, before, payload.model_dump(), project_id=project_id)
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

    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    crud.log(db, current_user, "删除问题", "issue", row_id, before, {})
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
    require_project_not_archived(project_id, db)

    before_status = row.status
    row.status = IF.normalize_status(payload.status)
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    crud.log(db, current_user, "更新问题状态", "issue", row.id,
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
    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    row.status = IF.STATUS_RESOLVED
    if payload.resolution:
        row.resolution = payload.resolution
    if payload.handler_reply:
        row.handler_reply = payload.handler_reply
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "标记已解决", "issue", row.id, before, crud.to_dict(row), project_id=project_id)
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
    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    row.status = IF.STATUS_CLOSED
    if payload.reason:
        row.resolution = payload.reason
    if payload.handler_reply:
        row.handler_reply = payload.handler_reply
    _sync_issue_closed_at(row)
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "关闭问题", "issue", row.id, before, crud.to_dict(row), project_id=project_id)
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
    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    row.helper = payload.helper
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "指派协助人", "issue", row.id, before,
             {"helper": payload.helper}, project_id=project_id)
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
    require_project_not_archived(project_id, db)
    before = crud.to_dict(row)
    row.issue_type = IF.TYPE_DECISION
    row.status = IF.STATUS_PENDING_DECISION
    row.need_decision_by = payload.need_decision_by
    if payload.note:
        existing = (row.resolution or "").strip()
        row.resolution = (existing + "\n" + payload.note).strip() if existing else payload.note
    row.edit_count = (row.edit_count or 0) + 1
    project_id = row.project_id
    crud.log(db, current_user, "上报企业教练决策", "issue", row.id, before, crud.to_dict(row), project_id=project_id)
    from ..services.notify import send as _notify, person_name_for_account, person_id_for_account, ceo_person_ids
    caller_name = person_name_for_account(current_user, db)
    caller_id = person_id_for_account(current_user, db)
    for ceo_id in ceo_person_ids(db):
        if ceo_id != caller_id:
            _notify(db, recipient_id=ceo_id, ntype="issue_needs_decision",
                    title=f"有问题需要您决策：{row.description[:40]}{'…' if len(row.description) > 40 else ''}",
                    body=f"上报人：{caller_name}，决策人：{payload.need_decision_by or '待定'}，专项：{row.special_project or ''}",
                    link=f"/project/{project_id}/issues" if project_id else "",
                    project_id=project_id)
    db.commit()
    return crud.to_dict(row)
