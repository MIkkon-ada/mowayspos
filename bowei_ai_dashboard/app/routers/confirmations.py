import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from .subtasks import _sync_parent_task_status
from ..database import get_db
from ..domain import issue_type as IT
from ..domain import issue_flow as IF
from ..domain import source_type as ST
from ..domain import submission_result_type as RT
from ..domain import submission_status as SS
from ..domain import task_status as TS
from ..permissions import (
    can_access_confirmation_center,
    can_assign_submission,
    get_current_user_name,
    get_user_context_from_db,
    require_project_owner_or_admin,
)
from ..time_utils import utc_now
from ..services.project_resolution import resolve_project_context
from ..archived_guard import require_project_not_archived
from ..services import policy as P
from ..services import workflow as W

router = APIRouter(prefix="/api/confirmations", tags=["confirmations"])

# ── Issue-type prefix table for plain-string subtask_issues ──
_ISSUE_PREFIX_TABLE: list[tuple[tuple[str, ...], str]] = [
    (("风险：", "风险:"), IF.TYPE_RISK),
    (("需决策：", "需决策:", "决策：", "决策:"), IF.TYPE_DECISION),
    (("待协调：", "待协调:", "协调：", "协调:"), IF.TYPE_COORDINATE),
    (("问题：", "问题:"), IF.TYPE_ISSUE),
]


def _parse_subtask_issue(item: object) -> dict | None:
    """Parse a subtask_issues item (str or dict) into {issue_type, description, priority}."""
    if isinstance(item, dict):
        desc = (item.get("description") or "").strip()
        if not desc:
            return None
        return {
            "issue_type": IT.normalize(item.get("issue_type")),
            "description": desc,
            "priority": str(item.get("priority") or "中"),
        }
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        for prefixes, itype in _ISSUE_PREFIX_TABLE:
            for prefix in prefixes:
                if text.startswith(prefix):
                    return {"issue_type": IT.normalize(itype), "description": text[len(prefix):].strip(), "priority": "中"}
        return {"issue_type": IT.TYPE_ISSUE, "description": text, "priority": "中"}
    return None


_ISSUE_STORAGE_LABELS: dict[str, str] = {
    IT.TYPE_ISSUE: IF.TYPE_ISSUE,
    IT.TYPE_RISK: IF.TYPE_RISK,
    IT.TYPE_COORDINATION: IF.TYPE_COORDINATE,
    IT.TYPE_DECISION: IF.TYPE_DECISION,
    IT.TYPE_UNKNOWN: IF.TYPE_ISSUE,
}


def _storage_issue_type(issue_type: str | None) -> str:
    return _ISSUE_STORAGE_LABELS.get(IT.normalize(issue_type), IF.TYPE_ISSUE)


def _extract_report_subtask_id(report: dict) -> int | None:
    """从 report 中读取 matched_subtask_id 或 related_subtask_id，没有则返回 None"""
    sid = report.get("matched_subtask_id") or report.get("related_subtask_id")
    if sid is not None:
        try:
            return int(sid)
        except (ValueError, TypeError):
            return None
    return None


def _resolve_report_related_subtask_id(
    db: Session,
    project_id: int | None,
    related_task_id: int | None,
    report: dict,
) -> int | None:
    """读取并校验 report 中的 related_subtask_id，合法返回 int，不合法抛 422，没有返回 None"""
    subtask_id = _extract_report_subtask_id(report)
    if subtask_id is None:
        return None
    crud.validate_subtask_link(db, project_id, related_task_id, subtask_id)
    return subtask_id


def _apply_related_subtask(obj, related_subtask_id: int | None) -> None:
    """设置对象的 related_subtask_id"""
    if related_subtask_id is not None:
        obj.related_subtask_id = related_subtask_id


def _issue_status_for(issue_type: str | None) -> str:
    return IF.STATUS_PENDING_DECISION if IT.is_decision(issue_type) else IF.STATUS_PENDING

# ── Confirmation-center tab mapping ──────────────────────────
TAB_STATUS_MAP: dict[str, frozenset[str]] = {
    "待审核": SS.TAB_PENDING_REVIEW,
    "流转中": SS.TAB_IN_FLIGHT,
    "已完成": SS.TAB_COMPLETED,
    "ceo":    SS.TAB_CEO_PENDING,
    "all":    SS.TAB_PENDING_REVIEW | SS.TAB_IN_FLIGHT | SS.TAB_COMPLETED,
}

_WITHDRAWABLE_STATUSES = SS.WITHDRAWABLE
_ACTIVE_STATUSES       = list(SS.ALL_ACTIVE)


def _load_submission(db: Session, submission_id: int) -> models.UpdateSubmission:
    row = db.get(models.UpdateSubmission, submission_id)
    if not row:
        raise HTTPException(404, "confirmation not found")
    return row




def _submission_project_context(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> dict:
    payload = json_payload if json_payload is not None else W.submission_result(row)
    return resolve_project_context(
        db,
        project_id=row.project_id,
        json_payload=payload,
        parent_task_id=row.related_task_id,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )


def _submission_project_id(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> int | None:
    return _submission_project_context(
        db,
        row,
        json_payload=json_payload,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )["project_id"]


def _submission_project_name(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> str:
    context = _submission_project_context(
        db,
        row,
        json_payload=json_payload,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )
    if context.get("project_name"):
        return context["project_name"]
    payload = json_payload if json_payload is not None else W.submission_result(row)
    task = payload.get("task") if isinstance(payload, dict) and isinstance(payload.get("task"), dict) else {}
    return (
        task.get("special_project")
        or payload.get("special_project")
        or task.get("project_name")
        or payload.get("project_name")
        or task.get("projectName")
        or payload.get("projectName")
        or ""
    )


def _resolve_pending_project_id(
    db: Session,
    project_id: int | None,
    special_project: str | None,
) -> int | None:
    if project_id is not None:
        return project_id
    if not special_project:
        return None
    return resolve_project_context(db, special_project=special_project)["project_id"]


def _require_submission_project_access(
    row: models.UpdateSubmission,
    context: dict,
    db: Session | None = None,
) -> int | None:
    project_id = _submission_project_id(db, row) if db is not None else P.project_id_of(row)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(422, "submission missing project_id")
    return project_id


def _require_submission_writable(
    row: models.UpdateSubmission,
    context: dict,
    db: Session,
) -> int | None:
    """AI 确认中心写操作专用：先做项目访问校验，再拦截归档项目写入。"""
    project_id = _require_submission_project_access(row, context, db)
    require_project_not_archived(project_id, db)
    return project_id


def _require_submission_owner_or_admin(
    row: models.UpdateSubmission,
    context: dict,
    current_user: str,
    db: Session,
) -> int | None:
    project_id = _require_submission_project_access(row, context, db)
    if project_id is None:
        return None
    require_project_owner_or_admin(current_user, project_id, db)
    return project_id
def _require_confirmation_center(context: dict) -> None:
    if context.get("is_tech_admin"):
        return
    if not can_access_confirmation_center(context):
        raise HTTPException(403, "permission denied")


def _require_owner_style_actor(context: dict) -> None:
    if context.get("is_ceo") and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")


def _can_owner_style_action(context: dict, row: models.UpdateSubmission, db: Session, *, allow_assign: bool = False) -> bool:
    if context.get("is_tech_admin"):
        return True
    if P.can_confirm(context, row, db):
        return True
    if allow_assign and can_assign_submission(context):
        return True
    return False


def _task_reports(data: dict) -> list[dict]:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        raise HTTPException(400, "task_reports must be a list")
    return reports


def _get_task_card(data: dict, card_index: int) -> tuple[list[dict], dict]:
    reports = _task_reports(data)
    if card_index < 0 or card_index >= len(reports):
        raise HTTPException(404, "task card not found")
    report = reports[card_index]
    if not isinstance(report, dict):
        raise HTTPException(400, "task card is not an object")
    return reports, report


def _mark_task_card(
    row: models.UpdateSubmission,
    data: dict,
    card_index: int,
    status: str,
    operator: str,
    note: str = "",
) -> None:
    reports, report = _get_task_card(data, card_index)
    report["confirmation_status"] = status
    report["confirmation_operator"] = operator
    report["confirmation_note"] = note
    report["confirmation_at"] = utc_now().isoformat()
    reports[card_index] = report
    data["task_reports"] = reports
    row.human_result_json = json.dumps(data, ensure_ascii=False)


def _all_task_cards_confirmed(data: dict) -> bool:
    reports = _task_reports(data)
    return bool(reports) and all(
        isinstance(report, dict) and report.get("confirmation_status") == "confirmed"
        for report in reports
    )


def _write_single_task_report(
    db: Session,
    row: models.UpdateSubmission,
    data: dict,
    report: dict,
    operator: str,
    effective_project_id: int | None,
    project_name: str,
    now: datetime,
) -> int | None:
    project = project_name
    task_id = row.related_task_id
    write_tr_achievements = bool(data.get("write_task_reports_achievements", True))
    write_tr_issues = bool(data.get("write_task_reports_issues", True))
    item_rt = report.get("result_type")

    if item_rt == RT.TYPE_SUGGEST_NEW_SUBTASK:
        parent_task_id = report.get("parent_task_id")
        if not parent_task_id:
            raise HTTPException(422, "suggest_new_subtask missing parent_task_id")
        parent_task = db.get(models.Task, int(parent_task_id))
        if parent_task and not parent_task.is_deleted:
            new_sub = models.SubTask(
                task_id=parent_task.id,
                title=str(report.get("title") or "new subtask")[:200],
                assignee=str(report.get("assignee") or row.submitter or ""),
                plan_time=str(report.get("plan_end") or ""),
                status=TS.S_IN_PROGRESS,
                source_submission_id=row.id,
            )
            db.add(new_sub)
            db.flush()
            _sync_parent_task_status(parent_task, db, operator)
            task_id = parent_task.id
            row.related_task_id = parent_task.id
            if write_tr_achievements:
                for ach_item in (report.get("achievements") or []):
                    if isinstance(ach_item, dict) and ach_item.get("name"):
                        ach_dict = dict(ach_item)
                        ach_dict.setdefault("special_project", project)
                        ach_dict.setdefault("owner", row.submitter or "")
                        ach = W.fulfill_or_create_achievement(
                            db, ach_dict, row.source_type, parent_task.id,
                            ach_dict.get("special_project") or project,
                            submission_id=row.id,
                        )
                        if ach:
                            ach.confirmed_by = operator
                            ach.confirmed_at = now
                            ach.related_subtask_id = new_sub.id
                            if effective_project_id and not ach.project_id:
                                ach.project_id = effective_project_id
            crud.log(
                db, operator, "confirmation_card_create_subtask", "subtask", new_sub.id,
                {}, {"title": new_sub.title, "task_id": parent_task.id, "from_submission": row.id},
                project_id=effective_project_id,
            )
        return task_id

    old_type = report.get("type", "progress")
    if item_rt not in (RT.TYPE_SUBTASK_PROGRESS, RT.TYPE_SUBTASK_COMPLETE, None):
        return task_id
    if item_rt is None and old_type != "progress":
        return task_id

    matched_id = report.get("matched_subtask_id")
    if not matched_id:
        return task_id
    subtask = db.get(models.SubTask, int(matched_id))
    if not subtask or subtask.is_deleted:
        raise HTTPException(422, "关键任务不存在或已删除。")

    # 校验 matched_subtask_id 与 重点工作/项目 一致性
    crud.validate_subtask_link(db, effective_project_id, subtask.task_id, int(matched_id))

    completed = (report.get("completed") or "").strip()
    if completed:
        existing = subtask.notes or ""
        subtask.notes = f"{existing}\n[{now.strftime('%Y-%m-%d')}] {completed}".strip()

    if item_rt == RT.TYPE_SUBTASK_COMPLETE:
        subtask.status = TS.S_COMPLETED
    elif item_rt is None and report.get("status_update"):
        subtask.status = report["status_update"]

    subtask.source_submission_id = row.id
    parent = db.get(models.Task, subtask.task_id)
    if parent:
        _sync_parent_task_status(parent, db, operator)
        task_id = parent.id
        row.related_task_id = parent.id

    if write_tr_achievements:
        for ach_item in (report.get("achievements") or []):
            if isinstance(ach_item, dict) and ach_item.get("name"):
                ach_dict = dict(ach_item)
                ach_dict.setdefault("special_project", project)
                ach_dict.setdefault("owner", row.submitter or "")
                ach = W.fulfill_or_create_achievement(
                    db, ach_dict, row.source_type, task_id,
                    ach_dict.get("special_project") or project,
                    submission_id=row.id,
                )
                if ach:
                    ach.confirmed_by = operator
                    ach.confirmed_at = now
                    ach.related_subtask_id = int(matched_id)
                    if effective_project_id and not ach.project_id:
                        ach.project_id = effective_project_id

    if write_tr_issues:
        for issue_item in (report.get("subtask_issues") or []):
            parsed = _parse_subtask_issue(issue_item)
            if not parsed:
                continue
            norm_type = parsed["issue_type"]
            issue = models.Issue(
                issue_type=_storage_issue_type(norm_type),
                description=parsed["description"],
                owner=row.submitter or "",
                priority=parsed["priority"],
                status=_issue_status_for(norm_type),
                special_project=project,
                source_type=ST.normalize(row.source_type or "人工录入"),
                confirmed_by=operator,
                source_submission_id=row.id,
                related_task_id=subtask.task_id,
            )
            issue.related_subtask_id = int(matched_id)
            if effective_project_id:
                issue.project_id = effective_project_id
            db.add(issue)

    return task_id


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/my-rejected")
def my_rejected(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """任意登录用户：查询打回给自己的提交，用于首页提醒。"""
    rows = (
        db.query(models.UpdateSubmission)
        .filter(models.UpdateSubmission.submitter == current_user)
        .order_by(models.UpdateSubmission.updated_at.desc())
        .all()
    )
    result = []
    for row in rows:
        if W.submission_status(row) not in (SS.RETURNED_TO_SUBMITTER | SS.WITHDRAWN):
            continue
        human = W.submission_result(row)
        item = crud.to_dict(row)
        item["special_project"] = _submission_project_name(db, row, json_payload=human)
        result.append(item)
    return result


@router.get("/counts")
def counts(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    _require_confirmation_center(context)

    # ── 快速路径：can_view_all 用户看全部提交，纯 SQL 聚合，无 Python 循环 ──
    if context["can_view_all"]:
        raw = (
            db.query(
                models.UpdateSubmission.confirm_status,
                func.count(models.UpdateSubmission.id),
            )
            .group_by(models.UpdateSubmission.confirm_status)
            .all()
        )
        status_counts: dict[str, int] = {(s or ""): c for s, c in raw}
        return {
            tab: sum(status_counts.get(s, 0) for s in statuses)
            for tab, statuses in TAB_STATUS_MAP.items()
        }

    # ── 普通用户：预加载角色，只拉三列，无额外 SQL ──────────────
    cache = P.preload_user_project_roles(context, db)
    sub_rows = db.query(
        models.UpdateSubmission.project_id,
        models.UpdateSubmission.submitter,
        models.UpdateSubmission.confirm_status,
    ).all()
    visible_statuses = [
        r.confirm_status or ""
        for r in sub_rows
        if P.can_view_batch(context, r.submitter, r.project_id, cache)
        and P.role_allows_batch(context, r.submitter, r.project_id, r.confirm_status, cache)
    ]
    return {
        tab: sum(1 for s in visible_statuses if s in statuses)
        for tab, statuses in TAB_STATUS_MAP.items()
    }


@router.get("/pending")
def pending(
    tab: str = "待审核",
    project_id: int | None = None,
    special_project: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    _require_confirmation_center(context)
    status_filter = TAB_STATUS_MAP.get(tab, TAB_STATUS_MAP["待审核"])

    effective_project_id = _resolve_pending_project_id(db, project_id, special_project)
    if project_id is None and special_project and effective_project_id is None:
        return []

    rows = (
        db.query(models.UpdateSubmission)
        .filter(models.UpdateSubmission.confirm_status.in_(list(status_filter)))
        .order_by(models.UpdateSubmission.updated_at.desc())
        .limit(500)
        .all()
    )
    # 预加载角色，消除循环 N+1
    cache = P.preload_user_project_roles(context, db)
    result = []
    for row in rows:
        if W.submission_status(row) not in status_filter:
            continue
        row_project_id = _submission_project_id(db, row)
        if not P.can_view_batch(context, row.submitter, row_project_id, cache):
            continue
        if effective_project_id is not None and row_project_id != effective_project_id:
            continue
        if not P.role_allows_batch(context, row.submitter, row_project_id, row.confirm_status, cache):
            continue
        human = W.submission_result(row)
        item = crud.to_dict(row)
        item["special_project"] = _submission_project_name(db, row, json_payload=human)
        item["related_task"] = human.get("related_task") or (human.get("task") or {}).get("key_task", "")
        result.append(item)
    return result


@router.get("/{submission_id}")
def detail(
    submission_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    _require_submission_project_access(row, context, db)
    _require_confirmation_center(context)
    if not P.can_view_in_center(context, row, db):
        raise HTTPException(403, "permission denied")
    data = crud.to_dict(row)
    data["ai_result"] = W.json_or_empty(row.ai_result_json)
    data["human_result"] = W.submission_result(row)
    return data


@router.post("/{submission_id}/save")
def save(
    submission_id: int,
    payload: schemas.ConfirmationSaveRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if context.get("is_ceo") and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    if not _can_owner_style_action(context, row, db, allow_assign=True):
        raise HTTPException(403, "permission denied")
    before = crud.to_dict(row)
    row.human_result_json = json.dumps(payload.human_result, ensure_ascii=False)
    row.confirm_status = SS.S_NEEDS_REVISION
    crud.log(db, current_user or "管理员", "confirmation_update", "confirmation", row.id, before, payload.human_result)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/confirm")
def confirm(
    submission_id: int,
    payload: schemas.ConfirmRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied — 仅项目负责人（owner）或管理员可确认入库")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)
    before = crud.to_dict(row)

    now = utc_now()
    data = W.submission_result(row)

    # Merge human_result from frontend (contains field edits and write-flags)
    if payload.human_result:
        hr = payload.human_result
        for k, v in hr.items():
            if k not in ("task", "achievements", "issues"):
                data[k] = v
        if "task" in hr and isinstance(hr["task"], dict):
            data["task"] = {**(data.get("task") or {}), **hr["task"]}
        if "achievements" in hr:
            data["achievements"] = hr["achievements"]
        if "issues" in hr:
            data["issues"] = hr["issues"]
        row.human_result_json = json.dumps(data, ensure_ascii=False)

    project_context = _submission_project_context(db, row, json_payload=data)
    effective_project_id = project_context["project_id"]
    task_id = row.related_task_id
    task_data = data.get("task") or {}
    task_before: dict = {}
    existing_task = None
    if task_id:
        existing_task = db.get(models.Task, task_id)
        if existing_task:
            task_before = crud.to_dict(existing_task)

    # ── 写入模式分支 ──────────────────────────────────────────
    write_mode = str(task_data.pop("write_mode", "task_new"))          # task_new | subtask_update | subtask_new | task_reports
    target_subtask_id = task_data.pop("target_subtask_id", None)
    target_task_id = task_data.pop("target_task_id", None)
    write_task = str(task_data.pop("write_task", "true")).lower() != "false"
    if write_mode == "task_new" and data.get("task_reports"):
        write_mode = "task_reports"
        write_task = False

    if data.get("result_type") == RT.TYPE_SUBTASK_STATUS_UPDATE:
        subtask_id = data.get("subtask_id")
        if not subtask_id:
            raise HTTPException(400, "subtask_status_update missing subtask_id")
        subtask = db.get(models.SubTask, int(subtask_id))
        if not subtask or subtask.is_deleted:
            raise HTTPException(404, "subtask not found")
        to_status = data.get("to_status") or data.get("suggested_status")
        if not to_status:
            raise HTTPException(400, "subtask_status_update missing to_status")
        subtask.status = TS.normalize(str(to_status))
        subtask.source_submission_id = row.id
        parent_task = db.get(models.Task, subtask.task_id)
        if parent_task:
            task_id = parent_task.id
            row.related_task_id = parent_task.id
            _sync_parent_task_status(parent_task, db, payload.operator)
        write_task = False

    elif write_mode == "subtask_update" and target_subtask_id:
        # 模式1：更新已有关键任务(subtask) 进度
        subtask = db.get(models.SubTask, int(target_subtask_id))
        if subtask and not subtask.is_deleted:
            completed = data.get("completed_items") or []
            notes_text = "；".join(completed) if completed else task_data.get("key_achievement", "")
            subtask.status = task_data.get("status") or subtask.status
            subtask.source_submission_id = row.id
            if notes_text:
                existing_notes = subtask.notes or ""
                subtask.notes = f"{existing_notes}\n[{now.strftime('%Y-%m-%d')}] {notes_text}".strip()
            parent_task = db.get(models.Task, subtask.task_id)
            if parent_task:
                _sync_parent_task_status(parent_task, db, payload.operator)
                task_id = parent_task.id
                row.related_task_id = parent_task.id
        write_task = False

    elif write_mode == "subtask_new" and target_task_id:
        # 模式2：在已有重点工作下新增关键任务
        parent_task = db.get(models.Task, int(target_task_id))
        if parent_task and not parent_task.is_deleted:
            title = task_data.get("key_task") or data.get("related_task") or "新增关键任务"
            new_sub = models.SubTask(
                task_id=parent_task.id,
                title=str(title)[:200],
                assignee=row.submitter or "",
                plan_time=task_data.get("plan_time") or "",
                status=task_data.get("status") or "进行中",
                completion_criteria=task_data.get("completion_standard") or "",
                notes=task_data.get("key_achievement") or "",
                source_submission_id=row.id,
            )
            db.add(new_sub)
            db.flush()
            _sync_parent_task_status(parent_task, db, payload.operator)
            task_id = parent_task.id
            row.related_task_id = parent_task.id
        write_task = False

    # 模式3（task_new）：新建重点工作（原有逻辑）
    task = None
    if write_task and task_data.get("key_task"):
        task = models.Task(**W.filtered_fields(models.Task, task_data))
        task.source_type = ST.normalize(row.source_type or "人工录入")
        task.submitter = row.submitter
        task.confirmed_by = payload.operator
        task.confirmed_at = now
        task.source_submission_id = row.id
        if effective_project_id and not task.project_id:
            task.project_id = effective_project_id
        if not task.coordinator:
            proj = db.get(models.Project, task.project_id) if task.project_id else None
            if proj and proj.coordinator:
                task.coordinator = proj.coordinator
        db.add(task)
        db.flush()
        task_id = task.id
        row.related_task_id = task.id

    project = _submission_project_name(db, row, json_payload=data)
    project_id = effective_project_id

    # ── 新格式：按 task_reports 更新匹配关键任务 ────────────────────
    key_task_issues_written = False
    if write_mode == "task_reports":
        write_tr_achievements = bool(data.get("write_task_reports_achievements", True))
        write_tr_issues = bool(data.get("write_task_reports_issues", True))
        task_reports_list = data.get("task_reports") or []

        # ── Pre-validate: every suggest_new_subtask item must carry parent_task_id ──
        for _report in task_reports_list:
            if not isinstance(_report, dict):
                continue
            if _report.get("result_type") == RT.TYPE_SUGGEST_NEW_SUBTASK:
                if not _report.get("parent_task_id"):
                    raise HTTPException(422, "建议新增关键任务缺少归属重点工作，请项目负责人先选择后再确认")

        for report in task_reports_list:
            if not isinstance(report, dict):
                continue

            item_rt = report.get("result_type")  # may be None for old-format items

            # ── suggest_new_subtask: create SubTask under owner-chosen parent ──
            if item_rt == RT.TYPE_SUGGEST_NEW_SUBTASK:
                parent_task_id = report.get("parent_task_id")
                parent_task = db.get(models.Task, int(parent_task_id))
                if parent_task and not parent_task.is_deleted:
                    new_sub = models.SubTask(
                        task_id=parent_task.id,
                        title=str(report.get("title") or "新增关键任务")[:200],
                        assignee=str(report.get("assignee") or row.submitter or ""),
                        plan_time=str(report.get("plan_end") or ""),
                        status="进行中",
                        source_submission_id=row.id,
                    )
                    db.add(new_sub)
                    db.flush()
                    _sync_parent_task_status(parent_task, db, payload.operator)
                    if not task_id:
                        task_id = parent_task.id
                        row.related_task_id = parent_task.id
                    if write_tr_achievements:
                        for ach_item in (report.get("achievements") or []):
                            if isinstance(ach_item, dict) and ach_item.get("name"):
                                ach_dict = dict(ach_item)
                                ach_dict.setdefault("special_project", project)
                                ach_dict.setdefault("owner", row.submitter or "")
                                ach = W.fulfill_or_create_achievement(
                                    db, ach_dict, row.source_type, parent_task.id,
                                    ach_dict.get("special_project") or project,
                                    submission_id=row.id,
                                )
                                if ach:
                                    ach.confirmed_by = payload.operator
                                    ach.confirmed_at = now
                                    ach.related_subtask_id = new_sub.id
                                    if effective_project_id and not ach.project_id:
                                        ach.project_id = effective_project_id
                    crud.log(
                        db, payload.operator, "confirmation_card_create_subtask", "subtask", new_sub.id,
                        {}, {"title": new_sub.title, "task_id": parent_task.id,
                              "from_submission": row.id},
                        project_id=effective_project_id,
                    )
                continue

            # ── subtask_progress / subtask_complete / old-format (no result_type) ──
            # Old format: type=="progress" with no result_type field
            old_type = report.get("type", "progress")
            if item_rt not in (RT.TYPE_SUBTASK_PROGRESS, RT.TYPE_SUBTASK_COMPLETE, None):
                continue
            if item_rt is None and old_type != "progress":
                continue

            matched_id = report.get("matched_subtask_id")
            if not matched_id:
                continue
            subtask = db.get(models.SubTask, int(matched_id))
            if not subtask or subtask.is_deleted:
                raise HTTPException(422, "关键任务不存在或已删除。")

            # 校验 matched_subtask_id 与 重点工作/项目 一致性，防止跨项目错配
            crud.validate_subtask_link(db, effective_project_id, subtask.task_id, int(matched_id))

            # Append progress note
            completed = (report.get("completed") or "").strip()
            if completed:
                existing = subtask.notes or ""
                subtask.notes = f"{existing}\n[{now.strftime('%Y-%m-%d')}] {completed}".strip()

            # Status update rules:
            # - subtask_complete → set 已完成
            # - subtask_progress → no status change
            # - old format (no result_type) → use status_update field (backward compat)
            if item_rt == RT.TYPE_SUBTASK_COMPLETE:
                subtask.status = TS.S_COMPLETED
            elif item_rt is None and report.get("status_update"):
                subtask.status = report["status_update"]
            # subtask_progress: deliberately skip status change

            subtask.source_submission_id = row.id
            parent = db.get(models.Task, subtask.task_id)
            if parent:
                _sync_parent_task_status(parent, db, payload.operator)
                if not task_id:
                    task_id = parent.id
                    row.related_task_id = parent.id

            # Write per-subtask achievements
            if write_tr_achievements:
                for ach_item in (report.get("achievements") or []):
                    if isinstance(ach_item, dict) and ach_item.get("name"):
                        ach_dict = dict(ach_item)
                        ach_dict.setdefault("special_project", project)
                        ach_dict.setdefault("owner", row.submitter or "")
                        ach = W.fulfill_or_create_achievement(
                            db, ach_dict, row.source_type, task_id,
                            ach_dict.get("special_project") or project,
                            submission_id=row.id,
                        )
                        if ach:
                            ach.confirmed_by = payload.operator
                            ach.confirmed_at = now
                            ach.related_subtask_id = int(matched_id)
                            if effective_project_id and not ach.project_id:
                                ach.project_id = effective_project_id

            # Write per-subtask issues
            if write_tr_issues:
                for issue_item in (report.get("subtask_issues") or []):
                    parsed = _parse_subtask_issue(issue_item)
                    if not parsed:
                        continue
                    norm_type = parsed["issue_type"]
                    issue = models.Issue(
                        issue_type=_storage_issue_type(norm_type),
                        description=parsed["description"],
                        owner=row.submitter or "",
                        priority=parsed["priority"],
                        status=_issue_status_for(norm_type),
                        special_project=project,
                        source_type=ST.normalize(row.source_type or "人工录入"),
                        confirmed_by=payload.operator,
                        source_submission_id=row.id,
                        related_task_id=subtask.task_id if subtask else None,
                    )
                    issue.related_subtask_id = int(matched_id)
                    if effective_project_id:
                        issue.project_id = effective_project_id
                    db.add(issue)

        # key_task_issues → 问题库
        if write_tr_issues:
            for ki in (data.get("key_task_issues") or []):
                if not isinstance(ki, dict) or not (ki.get("description") or "").strip():
                    continue
                norm_type = IT.normalize(ki.get("issue_type"))
                issue = models.Issue(
                    issue_type=_storage_issue_type(norm_type),
                    description=ki["description"].strip(),
                    owner=row.submitter or "",
                    helper="、".join(ki.get("need_coordination") or []),
                    priority=ki.get("priority") or "中",
                    status=_issue_status_for(norm_type),
                    special_project=project,
                    source_type=ST.normalize(row.source_type or "人工录入"),
                    confirmed_by=payload.operator,
                    source_submission_id=row.id,
                )
                if not ki.get("need_coordination"):
                    issue.helper = ""
                if effective_project_id:
                    issue.project_id = effective_project_id
                db.add(issue)

    # ── 旧格式：平铺 achievements / issues ───────────────────────
    else:
        for item in data.get("achievements", []):
            write_item = str(item.pop("write_achievement", "true")).lower() != "false"
            if write_item and item.get("name"):
                ach = W.fulfill_or_create_achievement(
                    db, item, row.source_type,
                    task_id, item.get("special_project") or project,
                    submission_id=row.id,
                )
                if ach:
                    ach.confirmed_by = payload.operator
                    ach.confirmed_at = now
                    if effective_project_id and not ach.project_id:
                        ach.project_id = effective_project_id

        for item in data.get("issues", []):
            write_item = str(item.pop("write_issue", "true")).lower() != "false"
            if write_item and item.get("description"):
                issue = models.Issue(**W.filtered_fields(models.Issue, item))
                issue.issue_type = _storage_issue_type(issue.issue_type)
                issue.source_type = ST.normalize(row.source_type or "人工录入")
                issue.confirmed_by = payload.operator
                issue.source_submission_id = row.id
                if effective_project_id and not issue.project_id:
                    issue.project_id = effective_project_id
                db.add(issue)

    if write_mode != "task_reports":
        for ki in (data.get("key_task_issues") or []):
            if not isinstance(ki, dict) or not (ki.get("description") or "").strip():
                continue
            norm_type = IT.normalize(ki.get("issue_type"))
            issue = models.Issue(
                issue_type=_storage_issue_type(norm_type),
                description=ki["description"].strip(),
                owner=row.submitter or "",
                helper="、".join(ki.get("need_coordination") or []),
                priority=ki.get("priority") or "中",
                status=_issue_status_for(norm_type),
                special_project=project,
                source_type=ST.normalize(row.source_type or "人工录入"),
                confirmed_by=payload.operator,
                source_submission_id=row.id,
            )
            if effective_project_id:
                issue.project_id = effective_project_id
            db.add(issue)

    row.human_result_json = json.dumps(data, ensure_ascii=False)
    row.confirm_status = SS.S_CONFIRMED
    row.confirmed_by = payload.operator
    row.confirmed_at = utc_now()

    if task_id:
        task_log_after = {
            "source": "AI确认中心",
            "submission_id": row.id,
            "submitter": row.submitter,
            "confirmed_by": payload.operator,
            "source_type": row.source_type,
            "title": row.title,
            "project": project,
            "task": crud.to_dict(task) if task is not None else (crud.to_dict(existing_task) if existing_task else task_data),
            "achievement": data.get("achievements", []),
            "issue": data.get("issues", []),
        }
        crud.log(db, payload.operator, "confirmation_ai_write_task", "task", task_id, task_before, task_log_after,
                 project_id=effective_project_id)
    crud.log(db, payload.operator, "confirmation_approve", "confirmation", row.id, before, data,
             project_id=effective_project_id)
    if row.submitter:
        from ..services.notify import send as _notify, person_id_for_account
        _notify(db, recipient_id=person_id_for_account(row.submitter, db),
                recipient=row.submitter, ntype="submission_confirmed",
                title=f"你的提交已确认入库：{row.title or '（无标题）'}",
                body="感谢你的反馈，提交内容已核实写入",
                link=f"/project/{project_id}/confirm" if project_id else "",
                project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/cards/{card_index}/confirm")
def confirm_task_card(
    submission_id: int,
    card_index: int,
    payload: schemas.ConfirmRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)

    before = crud.to_dict(row)
    effective_project_id = _submission_project_id(db, row)
    data = W.submission_result(row)
    if payload.human_result:
        data.update(payload.human_result)
    _, report = _get_task_card(data, card_index)
    project_context = _submission_project_context(db, row, json_payload=data)
    effective_project_id = project_context["project_id"]
    now = utc_now()
    task_id = _write_single_task_report(
        db,
        row,
        data,
        report,
        payload.operator,
        effective_project_id,
        _submission_project_name(db, row, json_payload=data),
        now,
    )
    _mark_task_card(row, data, card_index, "confirmed", payload.operator)
    if _all_task_cards_confirmed(data):
        row.confirm_status = SS.S_CONFIRMED
        row.confirmed_by = payload.operator
        row.confirmed_at = now
    else:
        row.confirm_status = SS.S_PENDING_OWNER

    crud.log(
        db, payload.operator, "confirmation_card_approve", "confirmation", row.id,
        before, {"card_index": card_index, "task_id": task_id},
        project_id=effective_project_id,
    )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/cards/{card_index}/reject")
def reject_task_card(
    submission_id: int,
    card_index: int,
    payload: schemas.RejectRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)

    before = crud.to_dict(row)
    effective_project_id = _submission_project_id(db, row)
    data = W.submission_result(row)
    _mark_task_card(row, data, card_index, "returned", payload.operator, payload.reason)
    row.confirm_status = SS.S_PENDING_OWNER
    row.reject_reason = payload.reason
    crud.log(
        db, payload.operator, "confirmation_card_return", "confirmation", row.id,
        before, {"card_index": card_index, "reason": payload.reason},
        project_id=effective_project_id,
    )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/cards/{card_index}/transfer-coordinator")
def transfer_task_card_to_coordinator(
    submission_id: int,
    card_index: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)

    before = crud.to_dict(row)
    data = W.submission_result(row)
    _mark_task_card(
        row, data, card_index, "transferred_to_coordinator",
        payload.operator, payload.note or "",
    )
    row.confirm_status = SS.S_PENDING_OWNER
    crud.log(
        db, payload.operator, "confirmation_card_forward_to_coordinator", "confirmation", row.id,
        before, {"card_index": card_index, "note": payload.note or ""},
        project_id=effective_project_id,
    )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/cards/{card_index}/escalate-ceo")
def escalate_task_card_to_ceo(
    submission_id: int,
    card_index: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if not (context.get("is_tech_admin") or P.can_escalate(context, row, db)):
        raise HTTPException(403, "permission denied")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)

    before = crud.to_dict(row)
    effective_project_id = _submission_project_id(db, row)
    data = W.submission_result(row)
    _mark_task_card(
        row, data, card_index, "pending_ceo_decision",
        payload.operator, payload.note or "",
    )
    row.confirm_status = SS.S_PENDING_OWNER
    crud.log(
        db, payload.operator, "confirmation_card_escalate_to_coach", "confirmation", row.id,
        before, {"card_index": card_index, "note": payload.note or ""},
        project_id=effective_project_id,
    )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/reject")
def reject(
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """打回给提交人补充。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied — 仅项目负责人（owner）可打回")
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_RETURNED
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_return", "confirmation", row.id, before, {"reason": payload.reason})
    if row.submitter:
        from ..services.notify import send as _notify, person_id_for_account
        _notify(db, recipient_id=person_id_for_account(row.submitter, db),
                recipient=row.submitter, ntype="submission_rejected",
                title=f"你的提交被打回：{row.title or '（无标题）'}",
                body=f"打回原因：{payload.reason or '未说明'}，请补充后重新提交",
                link=f"/project/{project_id}/confirm" if project_id else "",
                project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/resubmit")
def resubmit(
    submission_id: int,
    payload: schemas.ResubmitRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """提交人补充后重新提交：状态回到待负责人审核。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    _require_submission_writable(row, context, db)
    operator = payload.operator or current_user
    if row.submitter and row.submitter != operator:
        raise HTTPException(403, "只有原提交人可以重新提交")
    W.require_submission_status(row, SS.RETURNED_TO_SUBMITTER)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    if payload.human_result:
        new_result = dict(payload.human_result)
        if payload.supplement_note:
            new_result["supplement_note"] = payload.supplement_note
        row.human_result_json = json.dumps(new_result, ensure_ascii=False)
    elif payload.supplement_note:
        existing = W.json_or_empty(row.human_result_json or row.ai_result_json)
        existing["supplement_note"] = payload.supplement_note
        row.human_result_json = json.dumps(existing, ensure_ascii=False)
    row.confirm_status = SS.S_PENDING_OWNER
    row.reject_reason = None
    crud.log(db, operator, "confirmation_resubmit", "confirmation", row.id, before, {"note": payload.supplement_note or ""})
    if project_id:
        from ..services.notify import send as _notify, project_owner_ids, person_id_for_account
        submitter_id = person_id_for_account(operator, db)
        for owner_id in project_owner_ids(project_id, db):
            if owner_id != submitter_id:
                _notify(db, recipient_id=owner_id, ntype="submission_resubmitted",
                        title=f"提交人已重新提交：{row.title or '（无标题）'}",
                        body=f"提交人：{operator}，请前往 AI 确认中心处理",
                        link=f"/project/{project_id}/confirm",
                        project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/withdraw")
def withdraw(
    submission_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """提交人自行撤回。tech_admin 也可以代撤。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    _require_submission_writable(row, context, db)
    is_tech_admin = context.get("is_tech_admin", False)
    if row.submitter != current_user and not is_tech_admin:
        raise HTTPException(403, "只有原提交人或管理员可以撤回")
    W.require_submission_status(row, _WITHDRAWABLE_STATUSES)
    before = crud.to_dict(row)
    row.confirm_status = SS.S_WITHDRAWN
    crud.log(db, current_user, "confirmation_withdraw", "confirmation", row.id, before, {})
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/reject-final")
def reject_final(
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """永久不入库。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied — 仅项目负责人（owner）可永久拒绝")
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_PERMANENTLY_REJECTED
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_mark_not_imported", "confirmation", row.id, before, {"reason": payload.reason})
    if row.submitter:
        from ..services.notify import send as _notify, person_id_for_account
        _notify(db, recipient_id=person_id_for_account(row.submitter, db),
                recipient=row.submitter, ntype="submission_rejected",
                title=f"你的提交被标记为不入库：{row.title or '（无标题）'}",
                body=f"原因：{payload.reason or '未说明'}",
                link=f"/project/{project_id}/confirm" if project_id else "",
                project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/transfer-coordinator")
def transfer_coordinator(
    submission_id: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """转交统筹人给意见。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db):
        raise HTTPException(403, "permission denied — 仅项目负责人（owner）可转交统筹人")
    W.require_submission_status(row, SS.TRANSFERABLE_TO_COORDINATOR)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_WAITING_COORDINATOR
    if payload.note:
        row.reject_reason = payload.note
    crud.log(db, payload.operator, "confirmation_forward_to_coordinator", "confirmation", row.id, before, {"note": payload.note})
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/coordinator-feedback")
def coordinator_feedback(
    submission_id: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """统筹人反馈意见。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if not (context.get("is_tech_admin") or P.can_coordinate(context, row, db)):
        raise HTTPException(403, "permission denied — 仅该专项统筹人（coordinator）可反馈")
    W.require_submission_status(row, SS.WAITING_COORDINATOR_FEEDBACK)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_COORDINATOR_GIVEN
    row.coordinator_note = payload.note or ""
    crud.log(db, payload.operator, "confirmation_coordinator_feedback", "confirmation", row.id, before, {"note": payload.note})
    from ..services.notify import send as _notify, project_owner_ids, person_id_for_account
    caller_id = person_id_for_account(current_user or payload.operator, db)
    for owner_id in project_owner_ids(project_id, db):
        if owner_id != caller_id:
            _notify(db, recipient_id=owner_id, ntype="coordinator_feedback",
                    title=f"统筹人已反馈意见：{row.title or '（无标题）'}",
                    body=f"意见：{payload.note or '无'}，请前往 AI 确认中心处理",
                    link=f"/project/{project_id}/confirm",
                    project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/escalate-ceo")
def escalate_ceo(
    submission_id: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """上报企业教练决策。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if not (context.get("is_tech_admin") or P.can_escalate(context, row, db)):
        raise HTTPException(403, "permission denied — 仅项目负责人（owner）或超级管理员可上报企业教练")
    W.require_submission_status(row, SS.ESCALATABLE_TO_CEO)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_WAITING_CEO
    if payload.note:
        row.reject_reason = payload.note
    crud.log(db, payload.operator, "confirmation_escalate_to_coach", "confirmation", row.id, before, {"note": payload.note})
    from ..services.notify import send as _notify, project_coach_person_ids, person_name_for_account, person_id_for_account
    caller_name = person_name_for_account(current_user or payload.operator, db)
    caller_id = person_id_for_account(current_user or payload.operator, db)
    for coach_id in project_coach_person_ids(project_id, db):
        if coach_id != caller_id:
            _notify(db, recipient_id=coach_id, ntype="escalate_ceo",
                    title=f"有提交需要您决策：{row.title or '（无标题）'}",
                    body=f"上报人：{caller_name}，备注：{payload.note or '无'}",
                    link=f"/project/{project_id}/confirm" if project_id else "",
                    project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/ceo-decide")
def ceo_decide(
    submission_id: int,
    payload: schemas.WorkflowNoteRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """企业教练批示：批示后回到项目负责人执行确认写入。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if not (context.get("is_tech_admin") or P.can_ceo_decide(context, row, db)):
        raise HTTPException(403, "permission denied — 仅该项目企业教练或管理员可批示")
    W.require_submission_status(row, SS.WAITING_CEO_DECISION)
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    row.confirm_status = SS.S_CEO_DECIDED
    row.ceo_note = payload.note or ""
    crud.log(db, payload.operator, "confirmation_coach_decision", "confirmation", row.id, before, {"note": payload.note})
    from ..services.notify import send as _notify, project_owner_ids, person_id_for_account
    caller_id = person_id_for_account(current_user or payload.operator, db)
    for owner_id in project_owner_ids(project_id, db):
        if owner_id != caller_id:
            _notify(db, recipient_id=owner_id, ntype="ceo_decided",
                    title=f"企业教练已批示，请跟进处理：{row.title or '（无标题）'}",
                    body=f"批示：{payload.note or '无'}",
                    link=f"/project/{project_id}/confirm",
                    project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/mark-unrecognized")
def mark_unrecognized(
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """标记需人工处理（退回修订）。"""
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    if not _can_owner_style_action(context, row, db, allow_assign=True):
        raise HTTPException(403, "permission denied")
    before = crud.to_dict(row)
    row.confirm_status = SS.S_NEEDS_REVISION
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_mark_unrecognized", "confirmation", row.id, before, {"reason": payload.reason})
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


@router.post("/{submission_id}/assign")
def assign(
    submission_id: int,
    payload: schemas.AssignRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = _load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    _require_submission_writable(row, context, db)
    _require_confirmation_center(context)
    _require_owner_style_actor(context)
    if not _can_owner_style_action(context, row, db, allow_assign=True):
        raise HTTPException(403, "permission denied")
    before = crud.to_dict(row)
    project_id = _submission_project_id(db, row)
    data = W.submission_result(row)
    data["assigned_to"] = payload.assignee
    if "task" in data:
        data["task"]["owner"] = payload.assignee
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    row.confirm_status = SS.S_PENDING_OWNER
    crud.log(db, payload.operator, "confirmation_assign_owner", "confirmation", row.id, before, data)
    if payload.assignee:
        from ..services.notify import send as _notify, person_name_for_account, person_id_for_name, person_id_for_account
        caller_name = person_name_for_account(current_user or payload.operator, db)
        caller_id = person_id_for_account(current_user or payload.operator, db)
        assignee_id = person_id_for_name(payload.assignee, db)
        if payload.assignee != caller_name and assignee_id != caller_id:
            _notify(db, recipient_id=assignee_id, recipient=payload.assignee,
                    ntype="submission_assigned",
                    title=f"有提交指定由你负责：{row.title or '（无标题）'}",
                    body=f"指定人：{caller_name}，请前往 AI 确认中心处理",
                    link=f"/project/{project_id}/confirm" if project_id else "",
                    project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}

