import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..domain import source_type as ST
from ..domain import task_status as TS
from ..domain import project_lifecycle as PL
from ..permissions import (
    PROJECT_ROLE_COLLABORATOR,
    PROJECT_ROLE_COORDINATOR,
    PROJECT_ROLE_OWNER,
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    require_project_manager,
    require_project_access,
    require_project_owner_or_admin,
    require_tech_admin,
)
from ..time_utils import utc_now
from ..services.notify import (
    project_coach_person_ids,
    project_owner_ids,
    project_strict_owner_ids,
    send,
)
from ..services.project_close import (
    PROJECT_CLOSE_FROZEN_MESSAGE,
    evaluate_project_close,
    material_values,
    serialize_residual_items,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

_VALID_ROLES = {"project_ceo", "owner", "coordinator", "member"}
_LIFECYCLE_STATUSES = PL.ALL_STATUSES

# 旧展示常量 → 新 role key（用于 transition period 回落）
_OLD_ROLE_TO_KEY = {
    PROJECT_ROLE_OWNER:       "owner",
    PROJECT_ROLE_COORDINATOR: "coordinator",
    PROJECT_ROLE_COLLABORATOR: "member",
}


# ── 内部工具 ─────────────────────────────────────────────────

def _split_names(value) -> list[str]:
    source = str(value or "").strip()
    if not source:
        return []
    return [s.strip() for s in re.split(r"[,，、/;\n]+", source) if s.strip()]


def _join_names(names) -> str:
    seen: list[str] = []
    for n in names:
        n = str(n or "").strip()
        if n and n not in seen:
            seen.append(n)
    return "、".join(seen)


def _format_work_progress_plan_time(start: str | None, end: str | None) -> str:
    start_value = (start or "").strip()
    end_value = (end or "").strip()
    if start_value and end_value:
        return f"{start_value} ~ {end_value}"
    return start_value or end_value


def _person_id_for_name(name: str | None, db: Session) -> int | None:
    value = (name or "").strip()
    if not value:
        return None
    row = db.query(models.Person).filter(models.Person.name == value, models.Person.is_active.is_(True)).first()
    return row.id if row else None


def _helper_note(helper: str | None) -> str:
    value = (helper or "").strip()
    return f"协助人：{value}" if value else ""


def _normalize_lifecycle_status(value: str | None, default: str = "draft") -> str:
    return PL.normalize(value, default)


def _project_columns(db: Session) -> set[str]:
    try:
        # Inspect through the Session's current connection. Inspecting the
        # Engine can check out the same SQLite in-memory connection and issue
        # a rollback outside the Session, breaking the surrounding transaction.
        cols = inspect(db.connection()).get_columns("projects")
        return {str(col["name"]).lower() for col in cols}
    except Exception:
        return set()


def _has_project_column(db: Session, column: str) -> bool:
    return column.lower() in _project_columns(db)


def _update_project_columns(db: Session, project_id: int, **fields):
    updates = {}
    for key, value in fields.items():
        if value is None:
            continue
        if _has_project_column(db, key):
            updates[key] = value
    if not updates:
        return
    updates["id"] = project_id
    set_clause = ", ".join(f"{key} = :{key}" for key in updates if key != "id")
    db.execute(text(f"UPDATE projects SET {set_clause} WHERE id = :id"), updates)


def _set_project_lifecycle(
    project: models.Project,
    lifecycle_status: str,
    *,
    db: Session | None = None,
    project_id: int | None = None,
) -> str:
    """
    统一项目生命周期写入入口。

    内部以 status 作为主写字段，同时同步 lifecycle_status / is_active。
    若提供 db 与 project_id，则一并写入数据库列，避免各接口各写各的。
    """
    status = _normalize_lifecycle_status(lifecycle_status)
    project.status = status
    setattr(project, "lifecycle_status", status)
    project.is_active = status == PL.S_ACTIVE
    if db is not None and project_id is not None:
        _update_project_columns(
            db,
            project_id,
            status=status,
            lifecycle_status=status,
            is_active=project.is_active,
        )
    return status


def _require_project_not_close_frozen(project: models.Project) -> None:
    if PL.is_close_frozen(project.status):
        raise HTTPException(409, PROJECT_CLOSE_FROZEN_MESSAGE)


def _all_project_member_ids(project_id: int, db: Session) -> list[int]:
    rows = db.execute(
        text("SELECT DISTINCT person_id FROM project_members WHERE project_id = :pid AND person_id IS NOT NULL"),
        {"pid": project_id},
    ).fetchall()
    return [int(r[0]) for r in rows if r and r[0] is not None]


def _project_row_lifecycle(raw: dict) -> str:
    status = (raw.get("status") or "").strip()
    if status:
        return _normalize_lifecycle_status(status, "draft")
    lifecycle = (raw.get("lifecycle_status") or "").strip()
    if lifecycle:
        return _normalize_lifecycle_status(lifecycle, "draft")
    is_active = raw.get("is_active")
    if is_active is True:
        return "active"
    if is_active is False:
        return "archived"
    return "draft"


def _require_super_admin(current_user: str, db: Session):
    ctx = get_user_context_from_db(current_user, db)
    if not ctx.get("is_tech_admin"):
        raise HTTPException(403, "仅超级管理员可执行此操作")


def _require_project_manager(current_user: str, db: Session):
    """阶段 2B 收口：项目主数据管理仅 tech_admin。"""
    return require_tech_admin(current_user, db)


def _require_ceo_or_tech_admin(current_user: str, db: Session):
    ctx = get_user_context_from_db(current_user, db)
    if not (ctx.get("is_tech_admin") or ctx.get("is_ceo")):
        raise HTTPException(403, "仅 CEO 或超级管理员可执行此操作")


def _require_project_coach_or_tech_admin(current_user: str, project_id: int, db: Session):
    """审核立项权限：仅企业教练（project_ceo）或超级管理员可执行。

    公司CEO（system_role=company_ceo）不能仅凭系统角色审核立项。
    企业教练必须在该项目的 project_members 中有 project_ceo 角色。
    """
    ctx = get_user_context_from_db(current_user, db)
    if ctx.get("is_tech_admin"):
        return
    person_id = ctx.get("person_id")
    if person_id:
        roles = get_all_project_roles(person_id, project_id, db)
        if "project_ceo" in roles:
            return
    raise HTTPException(403, "仅企业教练或超级管理员可执行此操作")


def _require_project_source_manager(current_user: str, project_id: int, db: Session):
    """立项源头管理权限：super_admin 全阶段兜底；company_ceo 仅 draft 阶段可直接操作。

    项目下发后，编辑基础信息 / 配置成员等直接写操作需走变更申请流（本轮未实现），
    故非 draft 阶段仅 super_admin 可技术兜底，company_ceo / project_ceo / owner 均拒绝。
    """
    ctx = get_user_context_from_db(current_user, db)
    if ctx.get("is_tech_admin"):
        return
    if ctx.get("is_ceo"):
        status = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
        if status == "draft":
            return
    raise HTTPException(403, "项目已下发，当前仅支持查看。如需调整，请走变更申请流程。")


def _require_archive_via_approval(current_user: str, db: Session):
    """归档需审核流（本轮未实现），仅 super_admin 可技术兜底直接归档。

    company_ceo / project_ceo / owner 均不可直接归档，需提交归档申请由公司CEO审核。
    """
    ctx = get_user_context_from_db(current_user, db)
    if ctx.get("is_tech_admin"):
        return
    raise HTTPException(403, "项目归档需提交公司CEO审核。")


def _person_name(member: models.ProjectMember, db: Session) -> str:
    name = (member.person_name_snapshot or "").strip()
    if not name:
        person = db.get(models.Person, member.person_id)
        name = person.name if person else ""
    return name


def _rebuild_person_duties(db: Session):
    # 从 project_members 正规表读取，而非旧字符串字段（单源真相）
    members = (
        db.query(models.ProjectMember)
        .join(models.Project, models.ProjectMember.project_id == models.Project.id)
        .filter(models.Project.status != "archived")
        .all()
    )
    person_projects: dict[int, set[str]] = {}
    project_cache: dict[int, str] = {}
    for m in members:
        if m.project_id not in project_cache:
            proj = db.get(models.Project, m.project_id)
            project_cache[m.project_id] = proj.name if proj else ""
        proj_name = project_cache[m.project_id]
        if proj_name:
            person_projects.setdefault(m.person_id, set()).add(proj_name)

    for person in db.query(models.Person).all():
        assigned = sorted(person_projects.get(person.id, set()))
        person.special_project_duty = "、".join(assigned) if assigned else ""


def _sync_project_old_fields(
    project_id: int,
    db: Session,
    exclude_names: set[str] | None = None,
):
    """
    根据 project_members 重建旧字符串字段（smart merge）。
    exclude_names: DELETE 时传入被删人名，防止其被回填为历史数据。
    """
    project = db.get(models.Project, project_id)
    if not project:
        return

    members = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project_id)
        .all()
    )

    pm_owners:        set[str] = set()
    pm_coordinators:  set[str] = set()
    pm_collaborators: set[str] = set()
    pm_all:           set[str] = set()

    for m in members:
        name = _person_name(m, db)
        if not name:
            continue
        pm_all.add(name)
        if m.role == "owner":
            pm_owners.add(name)
        elif m.role == "coordinator":
            pm_coordinators.add(name)
        elif m.role == "member":
            pm_collaborators.add(name)

    legacy_owners        = set(_split_names(project.owners))        - pm_all
    legacy_coordinators  = set(_split_names(project.coordinator))   - pm_all
    legacy_collaborators = set(_split_names(project.collaborators)) - pm_all

    if exclude_names:
        legacy_owners        -= exclude_names
        legacy_coordinators  -= exclude_names
        legacy_collaborators -= exclude_names

    project.owners        = _join_names(sorted(pm_owners        | legacy_owners))
    project.coordinator   = _join_names(sorted(pm_coordinators  | legacy_coordinators))
    project.collaborators = _join_names(sorted(pm_collaborators | legacy_collaborators))

    _rebuild_person_duties(db)


def _member_to_dict(m: models.ProjectMember) -> dict:
    return {
        "id":                   m.id,
        "project_id":           m.project_id,
        "person_id":            m.person_id,
        "person_name_snapshot": m.person_name_snapshot or "",
        "role":                 m.role,
        "note":                 m.note or "",
        "joined_at":            m.joined_at.isoformat() if m.joined_at else None,
    }


# ── 6A：非归档项目最后 owner 保护 ────────────────────────────

def _is_active_project(project: models.Project) -> bool:
    """
    非归档项目都需要保留至少一名 owner。
    只有 archived 项目允许不保留 owner。
    """
    status = (getattr(project, "status", "") or "").strip()
    if not status:
        status = (getattr(project, "lifecycle_status", "") or "").strip()
    if status:
        return status != "archived"
    return bool(getattr(project, "is_active", False))


def _count_project_owners(db: Session, project_id: int) -> int:
    """统计 project_members 中该项目 role='owner' 的记录数。"""
    return (
        db.query(models.ProjectMember)
        .filter_by(project_id=project_id, role="owner")
        .count()
    )


def _ensure_not_removing_last_owner(
    db: Session,
    project: models.Project,
    member: models.ProjectMember,
) -> None:
    """
    如果该操作会移除 active 项目的最后一个 owner，抛出 409。
    归档项目不强制要求保留 owner；非 owner 角色操作直接跳过。
    """
    if not _is_active_project(project):
        return
    if member.role != "owner":
        return
    owner_count = _count_project_owners(db, project.id)
    if owner_count <= 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "该项目至少需要保留一名负责人，请先指定新负责人后再移除当前负责人",
                "project_id": project.id,
                "member_id": member.id,
                "role": member.role,
                "owner_count": owner_count,
            },
        )


# ── 新增：项目主数据读取辅助 ──────────────────────────────────

def _read_project_raw(project_id: int, db: Session) -> dict | None:
    """
    使用 raw SQL 读取项目基础字段，兼容 legacy / 旧库结构。
    保持对缺失列的容错，不改变现有接口返回。
    """
    cols = _project_columns(db)

    def _txt(name: str) -> str:
        if name in cols:
            return f"COALESCE({name}, '') AS {name}"
        return f"'' AS {name}"

    def _num(name: str, default: str = '0') -> str:
        if name in cols:
            return f"COALESCE({name}, {default}) AS {name}"
        return f"{default} AS {name}"

    if 'status' in cols:
        status_expr = "COALESCE(NULLIF(status, ''), CASE WHEN is_active = true THEN 'active' ELSE 'archived' END) AS status"
    else:
        status_expr = "CASE WHEN is_active = true THEN 'active' ELSE 'archived' END AS status"

    if 'lifecycle_status' in cols:
        lifecycle_expr = (
            "COALESCE(NULLIF(lifecycle_status, ''), "
            "COALESCE(NULLIF(status, ''), CASE WHEN is_active = true THEN 'active' ELSE 'archived' END)) AS lifecycle_status"
        )
    else:
        lifecycle_expr = "COALESCE(NULLIF(status, ''), CASE WHEN is_active = true THEN 'active' ELSE 'archived' END) AS lifecycle_status"

    try:
        row = db.execute(
            text(f'''
                SELECT id, name,
                       {_txt('code')},
                       {_txt('description')},
                       {status_expr},
                       {_txt('start_date')},
                       {_txt('end_date')},
                       {_txt('project_type')},
                       {_txt('client_name')},
                       {_txt('background')},
                       {_txt('objectives')},
                       {_txt('expected_outcomes')},
                       {lifecycle_expr},
                       {_txt('kickoff_date')},
                       {_txt('kickoff_by')},
                       {_txt('initiated_by')},
                       {_txt('coordinator')},
                       {_txt('owners')},
                       {_txt('collaborators')},
                       {_num('sort_order')},
                       is_active,
                       created_at, updated_at
                FROM projects WHERE id = :id
            '''),
            {"id": project_id},
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return dict(row._mapping)


def _get_user_roles(project_id: int, proj_name: str, context: dict, db: Session) -> list[str]:
    """返回当前用户在指定项目中的角色列表。"""
    if context.get("is_tech_admin"):
        return ["super_admin"]

    person_id = context.get("person_id")
    if person_id:
        rows = db.execute(
            text("SELECT role FROM project_members WHERE person_id = :pid AND project_id = :proj"),
            {"pid": person_id, "proj": project_id},
        ).fetchall()
        if rows:
            return [r[0] for r in rows]

    if context.get("is_ceo"):
        # 不再因 is_ceo 回落为 project_ceo：user_roles 只表达真实 project_members 角色。
        # company_ceo 的全局项目可见性由 _can_view_project 的 is_ceo 判断保障，不依赖 user_roles。
        pass

    return []


def _can_view_project(project_id: int, proj_name: str, context: dict, db: Session) -> bool:
    if context.get("is_tech_admin") or context.get("is_ceo"):
        return True
    return bool(_get_user_roles(project_id, proj_name, context, db))


def _member_summary(project_id: int, db: Session) -> dict:
    """项目成员数量摘要（按角色）。"""
    rows = db.execute(
        text("SELECT role, COUNT(*) FROM project_members WHERE project_id = :pid GROUP BY role"),
        {"pid": project_id},
    ).fetchall()
    counts: dict[str, int] = {r: 0 for r in _VALID_ROLES}
    for role, cnt in rows:
        if role in counts:
            counts[role] = cnt
    return counts


def _coach_names(project_id: int, db: Session) -> list[str]:
    """查询项目企业教练人名列表。"""
    rows = db.execute(
        text(
            "SELECT DISTINCT p.name "
            "FROM project_members pm JOIN people p ON pm.person_id = p.id "
            "WHERE pm.project_id = :pid AND pm.role = 'project_ceo' ORDER BY p.name"
        ),
        {"pid": project_id},
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def _project_response(raw: dict, user_roles: list[str], db: Session) -> dict:
    """将 raw SQL 结果整理成项目响应。"""
    project_id = raw["id"]
    member_counts = _member_summary(project_id, db)
    lifecycle_status = _project_row_lifecycle(raw)
    return {
        "id": raw["id"],
        "name": raw["name"],
        "code": raw["code"],
        "description": raw["description"],
        "status": raw["status"],
        "lifecycle_status": lifecycle_status,
        "start_date": raw["start_date"],
        "end_date": raw["end_date"],
        "project_type": raw.get("project_type", "") or "",
        "client_name": raw.get("client_name", "") or "",
        "background": raw.get("background", "") or "",
        "objectives": raw.get("objectives", "") or "",
        "expected_outcomes": raw.get("expected_outcomes", "") or "",
        "kickoff_date": raw.get("kickoff_date", "") or "",
        "kickoff_by": raw.get("kickoff_by", "") or "",
        "initiated_by": raw.get("initiated_by", "") or "",
        "sort_order": raw["sort_order"],
        "is_active": bool(raw["is_active"]),
        "created_at": str(raw["created_at"] or ""),
        "updated_at": str(raw["updated_at"] or ""),
        "user_roles": user_roles,
        "member_counts": member_counts,
        # coordinator 字段仅用于前端兼容展示。
        "coordinator": raw["coordinator"],
        "owners": _split_names(raw["owners"]),
        "collaborators": _split_names(raw["collaborators"]),
        "coaches": _coach_names(project_id, db),
    }


def _init_project_members(project_id: int, payload: "schemas.ProjectCreatePayload", db: Session):
    """创建项目时，批量写入 project_members 并同步旧字段。"""
    role_map = {
        "project_ceo": payload.project_ceo_ids,
        "owner":       payload.owner_ids,
        "coordinator": payload.coordinator_ids,
        "member":      payload.member_ids,
    }
    for role, ids in role_map.items():
        for person_id in (ids or []):
            person = db.get(models.Person, person_id)
            if not person:
                continue
            existing = (
                db.query(models.ProjectMember)
                .filter_by(project_id=project_id, person_id=person_id, role=role)
                .first()
            )
            if not existing:
                db.add(models.ProjectMember(
                    project_id=project_id,
                    person_id=person_id,
                    person_name_snapshot=person.name,
                    role=role,
                    joined_at=utc_now(),
                ))
    db.flush()
    _sync_project_old_fields(project_id, db)


# ── 5A：项目改名前置检查 ───────────────────────────────────────

def _save_work_progress_draft(
    project: models.Project,
    payload: schemas.ProjectProfilePayload,
    *,
    current_user: str,
    db: Session,
) -> None:
    drafts = payload.work_progress_draft or []
    if not drafts:
        return

    project_name = project.name or ""
    for task_draft in drafts:
        task_title = (task_draft.title or "").strip()
        if not task_title:
            continue

        task = (
            db.query(models.Task)
            .filter(
                models.Task.project_id == project.id,
                models.Task.key_task == task_title[:200],
                models.Task.is_deleted.is_(False),
            )
            .first()
        )
        if task is None:
            task = models.Task(project_id=project.id, key_task=task_title[:200])
            db.add(task)

        task.special_project = project_name
        task.completion_standard = (task_draft.description or "").strip()
        task.owner = (task_draft.owner or "").strip()
        task.owner_id = _person_id_for_name(task.owner, db)
        task.collaborators = (task_draft.helper or "").strip()
        task.plan_time = _format_work_progress_plan_time(task_draft.plan_start, task_draft.plan_end)
        task.status = task.status or TS.S_NOT_STARTED
        task.source_type = ST.MANUAL
        task.submitter = current_user
        task.edit_count = (task.edit_count or 0) + 1
        db.flush()

        for sub_draft in task_draft.subtasks or []:
            sub_title = (sub_draft.title or "").strip()
            if not sub_title:
                continue
            subtask = (
                db.query(models.SubTask)
                .filter(
                    models.SubTask.task_id == task.id,
                    models.SubTask.title == sub_title[:200],
                    models.SubTask.is_deleted.is_(False),
                )
                .first()
            )
            if subtask is None:
                subtask = models.SubTask(task_id=task.id, title=sub_title[:200], assignee="")
                db.add(subtask)

            subtask.title = sub_title[:200]
            subtask.assignee = (sub_draft.assignee or "").strip()
            subtask.assignee_id = _person_id_for_name(subtask.assignee, db)
            subtask.plan_time = _format_work_progress_plan_time(sub_draft.plan_start, sub_draft.plan_end)
            subtask.status = subtask.status or TS.S_NOT_STARTED
            subtask.completion_criteria = (sub_draft.evaluation_standard or "").strip()
            subtask.notes = _helper_note(sub_draft.helper)


def _extract_special_project_from_json(raw_json: str | None) -> list[str]:
    """
    从 JSON 字符串中递归提取所有 special_project 字段值。
    支持结构：
      {"special_project": "X"}
      {"task": {"special_project": "X"}}
      数组中每个元素包含 special_project
    解析失败静默返回空列表。
    """
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
    except Exception:
        return []

    results: list[str] = []

    def _walk(obj):
        if isinstance(obj, dict):
            val = obj.get("special_project")
            if isinstance(val, str) and val.strip():
                results.append(val.strip())
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return results


def _count_legacy_project_name_refs(db: Session, old_name: str) -> dict:
    """
    统计各表中仍以旧项目名为 special_project 且 project_id IS NULL 的记录数。
    update_submissions 使用 Python JSON 解析；其他表使用精确 SQL。
    返回：{"tasks": n, "issues": n, "achievements": n, "meetings": n, "update_submissions": n}
    """
    counts: dict[str, int] = {
        "tasks": 0, "issues": 0, "achievements": 0,
        "meetings": 0, "update_submissions": 0,
    }

    def _sql_count(table: str, col: str) -> int:
        row = db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE project_id IS NULL AND {col} = :name"),
            {"name": old_name},
        ).fetchone()
        return int(row[0]) if row else 0

    counts["tasks"]        = _sql_count("tasks",        "special_project")
    counts["issues"]       = _sql_count("issues",       "special_project")
    counts["achievements"] = _sql_count("achievements", "special_project")

    row = db.execute(
        text("SELECT COUNT(*) FROM meetings WHERE project_id IS NULL AND related_special_project = :name"),
        {"name": old_name},
    ).fetchone()
    counts["meetings"] = int(row[0]) if row else 0

    # update_submissions：优先 JSON 解析，逐行检查
    submission_match = 0
    rows = db.execute(
        text("SELECT human_result_json, ai_result_json FROM update_submissions WHERE project_id IS NULL"),
    ).fetchall()
    for human_json, ai_json in rows:
        matched = False
        for raw in (human_json, ai_json):
            if old_name in (_extract_special_project_from_json(raw)):
                matched = True
                break
        if matched:
            submission_match += 1
    counts["update_submissions"] = submission_match

    return counts


def _ensure_project_can_rename(db: Session, project, new_name: str) -> None:
    """
    检查改名是否安全：若任意表存在 project_id IS NULL 且 special_project = 旧名 的记录，
    抛出 HTTP 409，响应体包含各表残留数量和操作建议。
    """
    old_name = project.name
    legacy = _count_legacy_project_name_refs(db, old_name)
    total = sum(legacy.values())
    if total == 0:
        return

    raise HTTPException(
        status_code=409,
        detail={
            "message": "该项目还有未迁移的历史数据，请先执行 project_id 回填后再修改项目名称",
            "project_id": project.id,
            "old_name": old_name,
            "new_name": new_name,
            "legacy_counts": legacy,
            "suggestion": (
                "请先执行 migrate_project_members.py --report-only 和 --execute，"
                "确认历史数据已回填 project_id 后再改名"
            ),
        },
    )


# ── 端点：项目主数据 ───────────────────────────────────────────

@router.get("")
def list_projects(
    include_archived: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """
    列出当前用户可见的项目。
    - super_admin：全部项目
    - 其余角色：仅在 project_members 中参与的项目（+ 旧字段过渡兼容）
    """
    context = get_user_context_from_db(current_user, db)

    # 构建基础 ORM 查询（is_active 过滤）
    q = db.query(models.Project)
    if not include_archived:
        q = q.filter(models.Project.status != "archived")
    q = q.order_by(models.Project.sort_order, models.Project.id)

    if not context["can_view_all"]:
        person_id = context.get("person_id")

        # 从 project_members 取可见 project_id
        pm_ids: set[int] = set()
        if person_id:
            rows = db.execute(
                text("SELECT DISTINCT project_id FROM project_members WHERE person_id = :pid"),
                {"pid": person_id},
            ).fetchall()
            pm_ids = {r[0] for r in rows}

        # 过渡期：旧 visible_projects（从旧字符串字段推导）
        old_names = context.get("visible_projects") or []
        old_ids: set[int] = set()
        if old_names:
            old_rows = (
                db.query(models.Project.id)
                .filter(models.Project.name.in_(old_names))
                .all()
            )
            old_ids = {r[0] for r in old_rows}

        visible_ids = pm_ids | old_ids
        if not visible_ids:
            return []
        q = q.filter(models.Project.id.in_(visible_ids))

    projects = q.all()
    result = []
    for p in projects:
        raw = _read_project_raw(p.id, db)
        if not raw:
            continue
        user_roles = _get_user_roles(p.id, p.name, context, db)
        result.append(_project_response(raw, user_roles, db))
    return result


@router.post("")
def create_project(
    payload: schemas.ProjectCreatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """仅 CEO / 技术管理员可新建项目。"""
    _require_ceo_or_tech_admin(current_user, db)
    context = get_user_context_from_db(current_user, db)

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(422, "name 不能为空")
    if db.query(models.Project).filter_by(name=name).first():
        raise HTTPException(409, f"项目名称 '{name}' 已存在")

    # 新建默认进入 draft
    project = models.Project(
        name=name,
        sort_order=0,
    )
    db.add(project)
    db.flush()  # ?? project.id
    _set_project_lifecycle(project, "draft", db=db, project_id=project.id)

    _update_project_columns(
        db,
        project.id,
        code=(payload.code or "").strip(),
        description=(payload.description or "").strip(),
        start_date=(payload.start_date or "").strip(),
        end_date=(payload.end_date or "").strip(),
        project_type=(payload.project_type or "").strip(),
        client_name=(payload.client_name or "").strip(),
        background=(payload.background or "").strip(),
        objectives=(payload.objectives or "").strip(),
        expected_outcomes=(payload.expected_outcomes or "").strip(),
        initiated_by=context["name"] or current_user,
        kickoff_date="",
        kickoff_by="",
    )

    # 初始成员同步到 project_members
    _init_project_members(project.id, payload, db)

    crud.log(db, current_user, "create_project", "project", project.id, {}, {"name": name})
    db.commit()

    raw = _read_project_raw(project.id, db)
    return _project_response(raw, _get_user_roles(project.id, name, context, db), db)


@router.post("/batch-import")
def batch_import_projects(
    payload: schemas.ProjectBatchImportPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """
    批量导入：从 Excel 粘贴的结构化数据创建专项+关键任务+问题。
    专项已存在则复用，关键任务逐行创建，问题有内容则写入问题库。
    """
    _require_super_admin(current_user, db)

    projects_created = 0
    projects_matched = 0
    tasks_created = 0
    issues_created = 0
    skipped_rows = 0

    # 缓存本次已处理的项目，避免重复查库
    project_cache: dict[str, models.Project] = {}

    for row in payload.rows:
        proj_name = (row.project_name or "").strip()
        task_name = (row.key_task or "").strip()
        if not proj_name or not task_name:
            skipped_rows += 1
            continue

        # 找或建专项
        if proj_name not in project_cache:
            existing = db.query(models.Project).filter_by(name=proj_name).first()
            if existing:
                project_cache[proj_name] = existing
                projects_matched += 1
            else:
                proj = models.Project(name=proj_name, sort_order=0)
                if row.coordinator:
                    proj.coordinator = row.coordinator.strip()
                if row.owner:
                    proj.owners = row.owner.strip()
                if row.collaborators:
                    proj.collaborators = row.collaborators.strip()
                db.add(proj)
                db.flush()
                _set_project_lifecycle(proj, "active", db=db, project_id=proj.id)
                project_cache[proj_name] = proj
                projects_created += 1
                crud.log(db, current_user, "批量导入建项", "project", proj.id, {}, {"name": proj_name})

        proj = project_cache[proj_name]

        # 创建关键任务
        task = models.Task(
            project_id=proj.id,
            special_project=proj_name,
            key_task=task_name[:200],
            key_achievement=(row.key_achievement or "")[:200],
            completion_standard=row.completion_standard or "",
            coordinator=row.coordinator or "",
            owner=row.owner or "",
            collaborators=row.collaborators or "",
            plan_time=row.plan_time or "",
            status=row.status or "未开始",
            source_type=ST.normalize("批量导入"),
            submitter=current_user,
        )
        db.add(task)
        db.flush()
        tasks_created += 1
        crud.log(db, current_user, "批量导入建任务", "task", task.id, {}, {"key_task": task_name})

        # 创建问题（如有）
        issue_text = (row.issue or "").strip()
        if issue_text:
            issue = models.Issue(
                project_id=proj.id,
                special_project=proj_name,
                related_task_id=task.id,
                description=issue_text,
                owner=row.owner or "",
                source_type=ST.normalize("批量导入"),
                status="待处理",
                priority="中",
            )
            db.add(issue)
            issues_created += 1

    db.commit()
    return {
        "ok": True,
        "projects_created": projects_created,
        "projects_matched": projects_matched,
        "tasks_created": tasks_created,
        "issues_created": issues_created,
        "skipped_rows": skipped_rows,
    }


@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """列出项目成员。super_admin 或项目内成员可查看。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")

    context = get_user_context_from_db(current_user, db)
    if not _can_view_project(project_id, project.name, context, db):
        raise HTTPException(403, "permission denied — 仅项目成员可查看")

    members = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project_id)
        .order_by(models.ProjectMember.joined_at)
        .all()
    )
    return [
        {**_member_to_dict(m), "person_name_snapshot": _person_name(m, db)}
        for m in members
    ]


@router.post("/{project_id}/members")
def add_member(
    project_id: int,
    payload: schemas.ProjectMemberPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_source_manager(current_user, project_id, db)
    person = db.get(models.Person, payload.person_id)
    if not person:
        raise HTTPException(404, f"person id={payload.person_id} not found")
    if payload.role not in _VALID_ROLES:
        raise HTTPException(422, f"role 必须是 {sorted(_VALID_ROLES)} 之一")

    existing = (
        db.query(models.ProjectMember)
        .filter_by(project_id=project_id, person_id=payload.person_id, role=payload.role)
        .first()
    )
    if existing:
        raise HTTPException(409, f"{person.name} 在该项目已持有角色 {payload.role}")

    row = models.ProjectMember(
        project_id=project_id,
        person_id=payload.person_id,
        person_name_snapshot=person.name,
        role=payload.role,
        note=payload.note or "",
        joined_at=utc_now(),
    )
    db.add(row)
    db.flush()
    _sync_project_old_fields(project_id, db)
    crud.log(db, current_user, "add_project_member", "project_member", row.id, {}, _member_to_dict(row))
    db.commit()
    db.refresh(row)
    return _member_to_dict(row)


@router.patch("/{project_id}/members/{member_id}")
def update_member(
    project_id: int,
    member_id: int,
    payload: schemas.ProjectMemberPatchPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = db.get(models.ProjectMember, member_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "project member not found")
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_source_manager(current_user, project_id, db)

    before = _member_to_dict(row)
    if payload.role is not None:
        if payload.role not in _VALID_ROLES:
            raise HTTPException(422, f"role 必须是 {sorted(_VALID_ROLES)} 之一")
        if payload.role != row.role:
            # 6A: 当前是 owner 且要改成非 owner → 检查是否最后一个 owner
            if row.role == "owner":
                project = db.get(models.Project, project_id)
                if project:
                    _ensure_not_removing_last_owner(db, project, row)

            dup = (
                db.query(models.ProjectMember)
                .filter_by(project_id=project_id, person_id=row.person_id, role=payload.role)
                .first()
            )
            if dup:
                raise HTTPException(409, f"该成员在该项目已持有角色 {payload.role}")
        row.role = payload.role
    if payload.note is not None:
        row.note = payload.note

    _sync_project_old_fields(project_id, db)
    crud.log(db, current_user, "update_project_member", "project_member", row.id, before, _member_to_dict(row))
    db.commit()
    return _member_to_dict(row)


@router.delete("/{project_id}/members/{member_id}")
def remove_member(
    project_id: int,
    member_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = db.get(models.ProjectMember, member_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "project member not found")
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_source_manager(current_user, project_id, db)

    before = _member_to_dict(row)

    # 6A: 删除前检查是否最后一个 owner
    if project:
        _ensure_not_removing_last_owner(db, project, row)

    person_name = _person_name(row, db)
    db.delete(row)
    db.flush()

    _sync_project_old_fields(
        project_id, db,
        exclude_names={person_name} if person_name else None,
    )
    crud.log(db, current_user, "remove_project_member", "project_member", member_id, before, {})
    db.commit()
    return {"ok": True}


# ── 成员变更申请（N8-P1-P1A：仅 add member/coordinator）──────────

_MCR_ROLE_LABEL_CN = {
    "owner": "项目负责人",
    "coordinator": "统筹人",
    "member": "协同成员",
    "project_ceo": "企业教练",
}


def _mcr_to_dict(r: models.MemberChangeRequest, db: Session) -> dict:
    requester = db.get(models.Person, r.requester_person_id) if r.requester_person_id else None
    reviewer = db.get(models.Person, r.reviewer_person_id) if r.reviewer_person_id else None
    target = db.get(models.Person, r.target_person_id)
    project = db.get(models.Project, r.project_id)
    return {
        "id": r.id,
        "project_id": r.project_id,
        "project_name": project.name if project else "",
        "requester_person_id": r.requester_person_id,
        "requester_name": requester.name if requester else "",
        "target_person_id": r.target_person_id,
        "target_person_name": r.target_person_name or (target.name if target else ""),
        "action": r.action,
        "from_role": r.from_role,
        "to_role": r.to_role,
        "to_role_label": _MCR_ROLE_LABEL_CN.get(r.to_role, r.to_role),
        "reason": r.reason or "",
        "status": r.status,
        "reviewer_person_id": r.reviewer_person_id,
        "reviewer_name": reviewer.name if reviewer else "",
        "review_comment": r.review_comment or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
    }


@router.post("/{project_id}/member-change-requests")
def create_member_change_request(
    project_id: int,
    payload: schemas.MemberChangeRequestPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """发起添加普通成员申请。owner 发起→pending；project_ceo/super_admin 发起→自动通过。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)

    status = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if status == "draft":
        raise HTTPException(400, "草稿阶段请直接配置项目初始成员，无需发起变更申请。")
    if status == "archived":
        raise HTTPException(400, "归档项目不允许发起成员变更申请。")

    ctx = get_user_context_from_db(current_user, db)
    person_id = ctx.get("person_id")
    is_tech_admin = bool(ctx.get("is_tech_admin"))
    requester_roles = get_all_project_roles(person_id, project_id, db) if person_id else []
    if not (is_tech_admin or "owner" in requester_roles or "project_ceo" in requester_roles):
        raise HTTPException(403, "仅项目负责人或企业教练可发起成员变更申请。")

    to_role = (payload.to_role or "").strip()
    if to_role == "owner":
        raise HTTPException(400, "负责人变更暂不纳入普通成员变更申请。")
    if to_role == "project_ceo":
        raise HTTPException(400, "企业教练变更请联系超级管理员处理。")
    if to_role not in ("member", "coordinator"):
        raise HTTPException(422, "to_role 只能是 member 或 coordinator。")

    target = db.get(models.Person, payload.target_person_id)
    if not target:
        raise HTTPException(404, f"person id={payload.target_person_id} not found")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(422, "reason 不能为空")

    existing = (
        db.query(models.ProjectMember)
        .filter_by(project_id=project_id, person_id=payload.target_person_id, role=to_role)
        .first()
    )
    if existing:
        raise HTTPException(409, "该成员已拥有该项目角色。")

    pending_dup = (
        db.query(models.MemberChangeRequest)
        .filter_by(
            project_id=project_id,
            target_person_id=payload.target_person_id,
            action="add",
            to_role=to_role,
            status="pending",
        )
        .first()
    )
    if pending_dup:
        raise HTTPException(409, "该成员的相同角色添加申请已在审核中。")

    is_requester_project_ceo = "project_ceo" in requester_roles
    auto_approve = is_tech_admin or is_requester_project_ceo

    req = models.MemberChangeRequest(
        project_id=project_id,
        requester_person_id=person_id,
        action="add",
        target_person_id=payload.target_person_id,
        target_person_name=target.name,
        from_role="",
        to_role=to_role,
        reason=reason,
        status="approved" if auto_approve else "pending",
        reviewer_person_id=person_id if auto_approve else None,
        review_comment=("技术兜底自动通过" if is_tech_admin else "企业教练发起，自动通过") if auto_approve else "",
        reviewed_at=utc_now() if auto_approve else None,
    )
    db.add(req)
    db.flush()

    new_member = None
    if auto_approve:
        new_member = models.ProjectMember(
            project_id=project_id,
            person_id=payload.target_person_id,
            person_name_snapshot=target.name,
            role=to_role,
            joined_at=utc_now(),
        )
        db.add(new_member)
        db.flush()
        _sync_project_old_fields(project_id, db)
        crud.log(db, current_user, "approve_member_change_auto", "project_member", new_member.id, {}, _member_to_dict(new_member))

    crud.log(db, current_user, "create_member_change_request", "member_change_request", req.id, {}, _mcr_to_dict(req, db))
    db.commit()
    db.refresh(req)
    result = _mcr_to_dict(req, db)
    if new_member:
        db.refresh(new_member)
        result["new_member"] = _member_to_dict(new_member)
    return result


@router.get("/{project_id}/member-change-requests")
def list_member_change_requests(
    project_id: int,
    status: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """查看成员变更申请列表。super_admin/company_ceo/项目成员可查看。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    require_project_access(current_user, project_id, db)

    q = db.query(models.MemberChangeRequest).filter_by(project_id=project_id)
    if status:
        q = q.filter(models.MemberChangeRequest.status == status)
    reqs = q.order_by(models.MemberChangeRequest.created_at.desc()).all()
    return [_mcr_to_dict(r, db) for r in reqs]


@router.post("/{project_id}/member-change-requests/{request_id}/approve")
def approve_member_change_request(
    project_id: int,
    request_id: int,
    payload: schemas.MemberChangeReviewPayload | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """企业教练审核通过添加普通成员申请，写入 project_members。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_coach_or_tech_admin(current_user, project_id, db)

    req = db.get(models.MemberChangeRequest, request_id)
    if not req or req.project_id != project_id:
        raise HTTPException(404, "member change request not found")
    if req.status != "pending":
        raise HTTPException(409, f"申请当前状态为 {req.status}，不可重复审核")
    if req.action != "add":
        raise HTTPException(400, "本轮仅支持 add 申请审核")
    if req.to_role not in ("member", "coordinator"):
        raise HTTPException(400, "to_role 只能是 member 或 coordinator")

    target = db.get(models.Person, req.target_person_id)
    if not target:
        raise HTTPException(404, "target person not found")

    existing = (
        db.query(models.ProjectMember)
        .filter_by(project_id=project_id, person_id=req.target_person_id, role=req.to_role)
        .first()
    )
    if existing:
        raise HTTPException(409, "该成员已拥有该项目角色")

    ctx = get_user_context_from_db(current_user, db)
    new_member = models.ProjectMember(
        project_id=project_id,
        person_id=req.target_person_id,
        person_name_snapshot=target.name,
        role=req.to_role,
        joined_at=utc_now(),
    )
    db.add(new_member)
    db.flush()

    req.status = "approved"
    req.reviewer_person_id = ctx.get("person_id")
    req.reviewed_at = utc_now()
    if payload and payload.review_comment:
        req.review_comment = payload.review_comment

    _sync_project_old_fields(project_id, db)
    crud.log(db, current_user, "approve_member_change", "project_member", new_member.id, {}, _member_to_dict(new_member))
    db.commit()
    db.refresh(req)
    db.refresh(new_member)
    return {**_mcr_to_dict(req, db), "new_member": _member_to_dict(new_member)}


@router.post("/{project_id}/member-change-requests/{request_id}/reject")
def reject_member_change_request(
    project_id: int,
    request_id: int,
    payload: schemas.MemberChangeReviewPayload | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """企业教练拒绝添加普通成员申请。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_coach_or_tech_admin(current_user, project_id, db)

    req = db.get(models.MemberChangeRequest, request_id)
    if not req or req.project_id != project_id:
        raise HTTPException(404, "member change request not found")
    if req.status != "pending":
        raise HTTPException(409, f"申请当前状态为 {req.status}，不可重复审核")

    ctx = get_user_context_from_db(current_user, db)
    req.status = "rejected"
    req.reviewer_person_id = ctx.get("person_id")
    req.reviewed_at = utc_now()
    req.review_comment = (payload.review_comment if payload else "").strip()

    crud.log(db, current_user, "reject_member_change", "member_change_request", req.id, {"status": "pending"}, {"status": "rejected"})
    db.commit()
    db.refresh(req)
    return _mcr_to_dict(req, db)


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """项目详情。super_admin 或项目内成员可查看。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")

    context = get_user_context_from_db(current_user, db)
    if not _can_view_project(project_id, project.name, context, db):
        raise HTTPException(403, "permission denied — 仅项目成员可查看")

    raw = _read_project_raw(project_id, db)
    user_roles = _get_user_roles(project_id, project.name, context, db)
    return _project_response(raw, user_roles, db)


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: schemas.ProjectPatchPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """修改项目基本信息：super_admin、项目负责人、企业教练或创建人可操作。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    _require_project_source_manager(current_user, project_id, db)

    warnings: list[str] = []

    if payload.name is not None:
        new_name = payload.name.strip()
        if new_name and new_name != project.name:
            _ensure_project_can_rename(db, project, new_name)

            dup = db.query(models.Project).filter(
                models.Project.name == new_name,
                models.Project.id != project_id,
            ).first()
            if dup:
                raise HTTPException(409, f"项目名称 '{new_name}' 已被其他项目使用")
            project.name = new_name

    # Close/ended/archive transitions are managed by dedicated endpoints.
    # archived -> active remains temporarily compatible until P4-P3 restore API.
    forbidden_targets = {PL.S_PENDING_CLOSE, PL.S_ENDED, PL.S_ARCHIVED}
    for candidate in (payload.status, payload.lifecycle_status):
        if candidate is not None and str(candidate).strip() in forbidden_targets:
            raise HTTPException(409, PROJECT_CLOSE_FROZEN_MESSAGE)

    lifecycle_candidate = payload.status if payload.status is not None else payload.lifecycle_status
    if lifecycle_candidate is not None:
        lifecycle = _normalize_lifecycle_status(lifecycle_candidate, project.status or "draft")
        _set_project_lifecycle(project, lifecycle, db=db, project_id=project_id)

    updates: dict = {}
    if payload.code is not None: updates["code"] = payload.code.strip()
    if payload.description is not None: updates["description"] = payload.description.strip()
    if payload.start_date is not None: updates["start_date"] = payload.start_date.strip()
    if payload.end_date is not None: updates["end_date"] = payload.end_date.strip()
    if payload.project_type is not None: updates["project_type"] = payload.project_type.strip()
    if payload.client_name is not None: updates["client_name"] = payload.client_name.strip()
    if payload.background is not None: updates["background"] = payload.background.strip()
    if payload.objectives is not None: updates["objectives"] = payload.objectives.strip()
    if payload.expected_outcomes is not None: updates["expected_outcomes"] = payload.expected_outcomes.strip()

    if updates:
        _update_project_columns(db, project_id, **updates)

    crud.log(db, current_user, "update_project", "project", project_id, {}, payload.model_dump(exclude_none=True))
    db.commit()

    raw = _read_project_raw(project_id, db)
    return {**_project_response(raw, ["super_admin"], db), "warnings": warnings}


_CLOSE_REQUEST_STATUSES = {"pending", "approved", "rejected", "cancelled"}


def _project_close_project_lock_statement(project_id: int):
    return (
        select(models.Project)
        .where(models.Project.id == project_id)
        .with_for_update()
    )


def _project_close_request_lock_statement(project_id: int, request_id: int):
    return (
        select(models.ProjectCloseRequest)
        .where(
            models.ProjectCloseRequest.id == request_id,
            models.ProjectCloseRequest.project_id == project_id,
        )
        .with_for_update()
    )


def _lock_project_for_close(project_id: int, db: Session) -> models.Project | None:
    statement = _project_close_project_lock_statement(project_id).execution_options(
        populate_existing=True
    )
    return db.execute(statement).scalar_one_or_none()


def _lock_close_request(
    project_id: int,
    request_id: int,
    db: Session,
) -> models.ProjectCloseRequest | None:
    statement = _project_close_request_lock_statement(
        project_id,
        request_id,
    ).execution_options(populate_existing=True)
    return db.execute(statement).scalar_one_or_none()


def _close_request_for_project(
    project_id: int,
    request_id: int,
    db: Session,
) -> models.ProjectCloseRequest:
    request = db.get(models.ProjectCloseRequest, request_id)
    if not request or request.project_id != project_id:
        raise HTTPException(404, "project close request not found")
    return request


def _close_context(current_user: str, db: Session) -> dict:
    return get_user_context_from_db(current_user, db)


def _require_close_request_owner(current_user: str, project_id: int, db: Session) -> dict:
    context = _close_context(current_user, db)
    if context.get("is_tech_admin"):
        return context
    person_id = context.get("person_id")
    if person_id and "owner" in get_all_project_roles(person_id, project_id, db):
        return context
    raise HTTPException(403, "仅项目负责人或超级管理员可执行此操作")


def _require_original_close_requester(
    current_user: str,
    request: models.ProjectCloseRequest,
    db: Session,
) -> dict:
    context = _close_context(current_user, db)
    if context.get("is_tech_admin"):
        return context
    person_id = context.get("person_id")
    if (
        person_id
        and request.requester_person_id == person_id
        and "owner" in get_all_project_roles(person_id, request.project_id, db)
    ):
        return context
    raise HTTPException(403, "仅原申请人或超级管理员可执行此操作")


def _require_close_request_view(current_user: str, project: models.Project, db: Session) -> dict:
    context = _close_context(current_user, db)
    if not _can_view_project(project.id, project.name, context, db):
        raise HTTPException(403, "permission denied — 仅项目成员可查看")
    return context


def _close_state(request: models.ProjectCloseRequest, project: models.Project) -> dict:
    values, materials_valid = material_values(request)
    return {
        "request_status": request.status,
        "project_status": project.status,
        "reviewer_person_id": request.reviewer_person_id,
        "review_comment": request.review_comment or "",
        "summary": values["summary"],
        "objective_result": values["objective_result"],
        "unfinished_items": values["unfinished_items"],
        "remaining_risks": values["remaining_risks"],
        "handover_plan": values["handover_plan"],
        "retrospective": values["retrospective"],
        "materials_valid": materials_valid,
    }


def _close_datetime(value) -> str | None:
    return value.isoformat(timespec="seconds") + "Z" if value else None


def _close_request_response(
    request: models.ProjectCloseRequest,
    project: models.Project,
    db: Session,
) -> dict:
    values, _storage_valid = material_values(request)
    requester = db.get(models.Person, request.requester_person_id) if request.requester_person_id else None
    reviewer = db.get(models.Person, request.reviewer_person_id) if request.reviewer_person_id else None
    blockers, warnings = evaluate_project_close(db, project.id, request)
    return {
        "id": request.id,
        "project_id": project.id,
        "project_name": project.name,
        "project_status": project.status,
        "requester_person_id": request.requester_person_id,
        "requester_name": requester.name if requester else "",
        "summary": request.summary,
        "objective_result": request.objective_result,
        "unfinished_items": values["unfinished_items"],
        "remaining_risks": values["remaining_risks"],
        "handover_plan": request.handover_plan,
        "retrospective": request.retrospective,
        "status": request.status,
        "reviewer_person_id": request.reviewer_person_id,
        "reviewer_name": reviewer.name if reviewer else "",
        "review_comment": request.review_comment or "",
        "created_at": _close_datetime(request.created_at),
        "updated_at": _close_datetime(request.updated_at),
        "reviewed_at": _close_datetime(request.reviewed_at),
        "cancelled_at": _close_datetime(request.cancelled_at),
        "blockers": blockers,
        "warnings": warnings,
    }


def _close_link(project_id: int, request_id: int) -> str:
    return f"/home/projects?projectId={project_id}&closeRequestId={request_id}"


def _notify_close_people(
    db: Session,
    recipient_ids: list[int],
    *,
    operator_person_id: int | None,
    ntype: str,
    title: str,
    project: models.Project,
    request: models.ProjectCloseRequest,
) -> None:
    seen: set[int] = set()
    for recipient_id in recipient_ids:
        if not recipient_id or recipient_id == operator_person_id or recipient_id in seen:
            continue
        seen.add(recipient_id)
        send(
            db,
            recipient_id=recipient_id,
            ntype=ntype,
            title=title,
            body=f"项目《{project.name}》结束申请状态已更新。",
            link=_close_link(project.id, request.id),
            project_id=project.id,
        )


def _ensure_pending_close_pair(
    project: models.Project,
    request: models.ProjectCloseRequest,
) -> None:
    if request.status != "pending" or PL.normalize(project.status) != PL.S_PENDING_CLOSE:
        raise HTTPException(409, "结束申请已不处于待审核状态")


def _raise_close_blocked(blockers: list[dict]) -> None:
    raise HTTPException(409, {"code": "PROJECT_CLOSE_BLOCKED", "blockers": blockers})


@router.post("/{project_id}/close-requests", status_code=201)
def create_project_close_request(
    project_id: int,
    payload: schemas.ProjectCloseRequestCreatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    context = _require_close_request_owner(current_user, project_id, db)
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    if PL.normalize(project.status) != PL.S_ACTIVE:
        raise HTTPException(409, "仅进行中的项目可申请结束")
    if db.query(models.ProjectCloseRequest).filter_by(project_id=project_id, status="pending").first():
        raise HTTPException(409, "项目已有待审核的结束申请")

    material_data = payload.model_dump()
    blockers, _warnings = evaluate_project_close(db, project_id, material_data)
    if blockers:
        _raise_close_blocked(blockers)

    request = models.ProjectCloseRequest(
        project_id=project_id,
        requester_person_id=context.get("person_id"),
        summary=payload.summary,
        objective_result=payload.objective_result,
        unfinished_items_json=serialize_residual_items(payload.unfinished_items),
        remaining_risks_json=serialize_residual_items(payload.remaining_risks),
        handover_plan=payload.handover_plan,
        retrospective=payload.retrospective,
        status="pending",
    )
    db.add(request)
    db.flush()
    before = _close_state(request, project)
    _set_project_lifecycle(project, PL.S_PENDING_CLOSE, db=db, project_id=project_id)
    after = _close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_create",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    _notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_requested",
        title="项目结束申请待审核",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return _close_request_response(request, project, db)


@router.get("/{project_id}/close-requests")
def list_project_close_requests(
    project_id: int,
    status: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_close_request_view(current_user, project, db)
    if status is not None and status not in _CLOSE_REQUEST_STATUSES:
        raise HTTPException(422, "invalid close request status")
    query = db.query(models.ProjectCloseRequest).filter_by(project_id=project_id)
    if status is not None:
        query = query.filter(models.ProjectCloseRequest.status == status)
    requests = query.order_by(
        models.ProjectCloseRequest.created_at.desc(),
        models.ProjectCloseRequest.id.desc(),
    ).all()
    return [_close_request_response(request, project, db) for request in requests]


@router.get("/{project_id}/close-requests/{request_id}")
def get_project_close_request(
    project_id: int,
    request_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    request = _close_request_for_project(project_id, request_id, db)
    _require_close_request_view(current_user, project, db)
    return _close_request_response(request, project, db)


@router.patch("/{project_id}/close-requests/{request_id}")
def update_project_close_request(
    project_id: int,
    request_id: int,
    payload: schemas.ProjectCloseRequestUpdatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = _lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    context = _require_original_close_requester(current_user, request, db)
    _ensure_pending_close_pair(project, request)

    current, _valid = material_values(request)
    updates = payload.model_dump(exclude_unset=True)
    current.update(updates)
    try:
        merged = schemas.ProjectCloseRequestCreatePayload.model_validate(current)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc

    before = _close_state(request, project)
    request.summary = merged.summary
    request.objective_result = merged.objective_result
    request.unfinished_items_json = serialize_residual_items(merged.unfinished_items)
    request.remaining_risks_json = serialize_residual_items(merged.remaining_risks)
    request.handover_plan = merged.handover_plan
    request.retrospective = merged.retrospective
    after = _close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_update",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    _notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_request_updated",
        title="项目结束材料已更新",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return _close_request_response(request, project, db)


@router.post("/{project_id}/close-requests/{request_id}/cancel")
def cancel_project_close_request(
    project_id: int,
    request_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = _lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    context = _require_original_close_requester(current_user, request, db)
    _ensure_pending_close_pair(project, request)
    before = _close_state(request, project)
    request.status = "cancelled"
    request.cancelled_at = utc_now()
    _set_project_lifecycle(project, PL.S_ACTIVE, db=db, project_id=project_id)
    after = _close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_cancel",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    _notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_cancelled",
        title="项目结束申请已取消",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return _close_request_response(request, project, db)


@router.post("/{project_id}/close-requests/{request_id}/approve")
def approve_project_close_request(
    project_id: int,
    request_id: int,
    payload: schemas.ProjectCloseReviewPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_coach_or_tech_admin(current_user, project_id, db)
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = _lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    context = _close_context(current_user, db)
    _ensure_pending_close_pair(project, request)
    blockers, _warnings = evaluate_project_close(db, project_id, request)
    if blockers:
        _raise_close_blocked(blockers)

    before = _close_state(request, project)
    request.status = "approved"
    request.reviewer_person_id = context.get("person_id")
    request.review_comment = payload.review_comment
    request.reviewed_at = utc_now()
    _set_project_lifecycle(project, PL.S_ENDED, db=db, project_id=project_id)
    after = _close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_approve",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    _notify_close_people(
        db,
        _all_project_member_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_approved",
        title="项目结束申请已批准",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return _close_request_response(request, project, db)


@router.post("/{project_id}/close-requests/{request_id}/reject")
def reject_project_close_request(
    project_id: int,
    request_id: int,
    payload: schemas.ProjectCloseReviewPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_coach_or_tech_admin(current_user, project_id, db)
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = _lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    context = _close_context(current_user, db)
    _ensure_pending_close_pair(project, request)
    if not payload.review_comment:
        raise HTTPException(422, "退回结束申请必须填写审核意见")

    before = _close_state(request, project)
    request.status = "rejected"
    request.reviewer_person_id = context.get("person_id")
    request.review_comment = payload.review_comment
    request.reviewed_at = utc_now()
    _set_project_lifecycle(project, PL.S_ACTIVE, db=db, project_id=project_id)
    after = _close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_reject",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    recipients = [request.requester_person_id, *project_strict_owner_ids(project_id, db)]
    _notify_close_people(
        db,
        [person_id for person_id in recipients if person_id],
        operator_person_id=context.get("person_id"),
        ntype="project_close_rejected",
        title="项目结束申请已退回",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return _close_request_response(request, project, db)


@router.post("/{project_id}/archive")
def archive_project(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """技术兜底归档：仅 super_admin 可执行 ended -> archived。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_archive_via_approval(current_user, db)
    project = _lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")

    lifecycle = PL.normalize(project.status)
    if lifecycle != PL.S_ENDED:
        raise HTTPException(409, "仅已结束项目可以归档")

    _set_project_lifecycle(project, "archived", db=db, project_id=project_id)
    crud.log(db, current_user, "archive_project", "project", project_id, {"is_active": True}, {"is_active": False})
    db.commit()

    return {"ok": True, "project_id": project_id, "status": "archived"}


def _project_members_to_notify(project_id: int, db: Session) -> list[int]:
    ids = _all_project_member_ids(project_id, db)
    if ids:
        return ids
    return project_owner_ids(project_id, db)


def _notify_people(db: Session, person_ids: list[int], *, ntype: str, title: str, body: str, link: str, project_id: int) -> None:
    for pid in person_ids:
        send(db, recipient_id=pid, ntype=ntype, title=title, body=body, link=link, project_id=project_id)


@router.post("/{project_id}/dispatch")
def dispatch_project(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """CEO 下发项目给负责人。"""
    _require_ceo_or_tech_admin(current_user, db)

    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    lifecycle = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if lifecycle == "archived":
        raise HTTPException(409, "已归档项目不可下发")
    if lifecycle == "active":
        raise HTTPException(409, "项目已启动，无需重新下发")

    # 兜底校验：下发前必须已配置企业教练(project_ceo)和负责人(owner)
    # super_admin / company_ceo 也不能绕过此业务校验
    _role_counts = _member_summary(project_id, db)
    if _role_counts.get("project_ceo", 0) <= 0:
        raise HTTPException(409, "请先配置企业教练后再下发项目。")
    if _role_counts.get("owner", 0) <= 0:
        raise HTTPException(409, "请先配置项目负责人后再下发项目。")

    _set_project_lifecycle(project, "dispatched", db=db, project_id=project_id)
    recipient_ids = project_owner_ids(project_id, db)
    _notify_people(
        db,
        recipient_ids,
        ntype="project_dispatch",
        title="项目下发通知",
        body=f"项目《{project.name}》已下发，请负责人补全立项信息",
        link=f"/home/dashboard?projectId={project_id}",
        project_id=project_id,
    )
    crud.log(db, current_user, "dispatch_project", "project", project_id, {"status": lifecycle}, {"status": "dispatched"})
    db.commit()
    return {"ok": True, "dispatched_to": len(recipient_ids)}


@router.post("/{project_id}/owner-submit")
def owner_submit_project_profile(
    project_id: int,
    payload: schemas.ProjectProfilePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """负责人提交立项信息，进入待审核。"""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    require_project_owner_or_admin(current_user, project_id, db)

    lifecycle = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if lifecycle == "archived":
        raise HTTPException(409, "已归档项目不可提交")
    if lifecycle == "pending_review":
        raise HTTPException(409, "项目已在审核中")

    _set_project_lifecycle(project, "pending_review", db=db, project_id=project_id)
    _update_project_columns(
        db,
        project_id,
        project_type=(payload.project_type or "").strip() if payload.project_type is not None else None,
        client_name=(payload.client_name or "").strip() if payload.client_name is not None else None,
        background=(payload.background or "").strip() if payload.background is not None else None,
        objectives=(payload.objectives or "").strip() if payload.objectives is not None else None,
        expected_outcomes=(payload.expected_outcomes or "").strip() if payload.expected_outcomes is not None else None,
        start_date=(payload.start_date or "").strip() if payload.start_date is not None else None,
        end_date=(payload.end_date or "").strip() if payload.end_date is not None else None,
        description=(payload.description or "").strip() if payload.description is not None else None,
    )
    _save_work_progress_draft(project, payload, current_user=current_user, db=db)
    crud.log(db, current_user, "owner_submit_project", "project", project_id, {"status": lifecycle}, {"status": "pending_review"})
    db.commit()

    raw = _read_project_raw(project_id, db)
    result = _project_response(raw, _get_user_roles(project_id, project.name, get_user_context_from_db(current_user, db), db), db)
    result["submitted_for_review"] = True
    return result


@router.post("/{project_id}/return")
def return_project(
    project_id: int,
    payload: schemas.ProjectProfilePayload | None = None,
    reason: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """企业教练 / 超级管理员将项目启动申请退回给负责人。"""
    _require_project_coach_or_tech_admin(current_user, project_id, db)

    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    lifecycle = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if lifecycle == "archived":
        raise HTTPException(409, "已归档项目不可退回")

    payload = payload or schemas.ProjectProfilePayload()
    _set_project_lifecycle(project, "returned", db=db, project_id=project_id)
    _update_project_columns(
        db,
        project_id,
        project_type=(payload.project_type or "").strip() if payload.project_type is not None else None,
        client_name=(payload.client_name or "").strip() if payload.client_name is not None else None,
        background=(payload.background or "").strip() if payload.background is not None else None,
        objectives=(payload.objectives or "").strip() if payload.objectives is not None else None,
        expected_outcomes=(payload.expected_outcomes or "").strip() if payload.expected_outcomes is not None else None,
        start_date=(payload.start_date or "").strip() if payload.start_date is not None else None,
        end_date=(payload.end_date or "").strip() if payload.end_date is not None else None,
        description=(payload.description or "").strip() if payload.description is not None else None,
    )
    recipient_ids = project_owner_ids(project_id, db)
    _notify_people(
        db,
        recipient_ids,
        ntype="project_returned",
        title="项目启动申请已退回",
        body=f"项目《{project.name}》需要补充后重新提交{f'，原因：{reason}' if reason else ''}",
        link=f"/home/dashboard?projectId={project_id}",
        project_id=project_id,
    )
    crud.log(db, current_user, "return_project", "project", project_id, {"status": lifecycle, "reason": reason or ""}, {"status": "returned"})
    db.commit()

    raw = _read_project_raw(project_id, db)
    return _project_response(raw, _get_user_roles(project_id, project.name, get_user_context_from_db(current_user, db), db), db)


@router.post("/{project_id}/approve")
def approve_project(
    project_id: int,
    payload: schemas.ProjectProfilePayload | None = None,
    kickoff_date: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """企业教练审核通过并确立项目。"""
    _require_project_coach_or_tech_admin(current_user, project_id, db)

    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    lifecycle = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if lifecycle == "archived":
        raise HTTPException(409, "已归档项目不可启动")

    payload = payload or schemas.ProjectProfilePayload()
    _set_project_lifecycle(project, "active", db=db, project_id=project_id)
    kickoff_value = (kickoff_date or utc_now().date().isoformat()).strip()
    current_name = get_user_context_from_db(current_user, db)["name"] or current_user
    _update_project_columns(
        db,
        project_id,
        kickoff_date=kickoff_value,
        kickoff_by=current_name,
        project_type=(payload.project_type or "").strip() if payload.project_type is not None else None,
        client_name=(payload.client_name or "").strip() if payload.client_name is not None else None,
        background=(payload.background or "").strip() if payload.background is not None else None,
        objectives=(payload.objectives or "").strip() if payload.objectives is not None else None,
        expected_outcomes=(payload.expected_outcomes or "").strip() if payload.expected_outcomes is not None else None,
        start_date=(payload.start_date or "").strip() if payload.start_date is not None else None,
        end_date=(payload.end_date or "").strip() if payload.end_date is not None else None,
        description=(payload.description or "").strip() if payload.description is not None else None,
    )

    member_ids = _project_members_to_notify(project_id, db)
    _notify_people(
        db,
        member_ids,
        ntype="project_kickoff",
        title="项目已启动",
        body=f"项目《{project.name}》已审核通过并正式启动",
        link=f"/home/dashboard?projectId={project_id}",
        project_id=project_id,
    )
    crud.log(db, current_user, "approve_project", "project", project_id, {"status": lifecycle}, {"status": "active"})
    db.commit()

    raw = _read_project_raw(project_id, db)
    return _project_response(raw, _get_user_roles(project_id, project.name, get_user_context_from_db(current_user, db), db), db)


@router.post("/{project_id}/kickoff")
def kickoff_project(
    project_id: int,
    kickoff_date: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """技术兜底：直接将项目切换为 active。仅超级管理员可执行，正常流程不应使用。"""
    _require_super_admin(current_user, db)

    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    _require_project_not_close_frozen(project)
    lifecycle = _project_row_lifecycle(_read_project_raw(project_id, db) or {})
    if lifecycle == "archived":
        raise HTTPException(409, "已归档项目不可启动")

    _set_project_lifecycle(project, "active", db=db, project_id=project_id)
    kickoff_value = (kickoff_date or utc_now().date().isoformat()).strip()
    current_name = get_user_context_from_db(current_user, db)["name"] or current_user
    _update_project_columns(
        db,
        project_id,
        kickoff_date=kickoff_value,
        kickoff_by=current_name,
    )

    member_ids = _project_members_to_notify(project_id, db)
    _notify_people(
        db,
        member_ids,
        ntype="project_kickoff",
        title="项目已启动",
        body=f"项目《{project.name}》已正式启动",
        link=f"/home/dashboard?projectId={project_id}",
        project_id=project_id,
    )
    crud.log(db, current_user, "kickoff_project", "project", project_id, {"status": lifecycle}, {"status": "active"})
    db.commit()

    raw = _read_project_raw(project_id, db)
    return _project_response(raw, _get_user_roles(project_id, project.name, get_user_context_from_db(current_user, db), db), db)


@router.get("/{project_id}/capabilities")
def project_capabilities(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """
    返回当前用户在该项目的能力标志位。
    前端直接消费，无需自行推算角色 → 权限逻辑。

    Fields:
      roles            当前用户在项目中的角色列表
      canSubmit        可提交进展更新
      canConfirm       可确认/打回/转交提交
      canCoordinate    可作为统筹人提供反馈
      canEscalateToCEO 可上报企业教练决策
      canCeoDecide     可作为企业教练批示
      canViewCenter    可进入AI 确认中心
      pendingCount     待处理（ALL_ACTIVE）提交数
    """
    from ..permissions import (
        can_access_confirmation_center,
        can_confirm_submission_by_project,
        can_coordinator_feedback_by_project,
        can_escalate_to_ceo_by_project,
        can_ceo_decide_by_project,
    )
    from ..services.policy import (
        user_roles_in_project,
        can_submit_to_project,
    )
    from ..domain import submission_status as SS

    context = get_user_context_from_db(current_user, db)

    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    require_project_access(current_user, project_id, db)

    roles = sorted(user_roles_in_project(context, project_id, db))

    pending_count = (
        db.query(models.UpdateSubmission)
        .filter(
            models.UpdateSubmission.project_id == project_id,
            models.UpdateSubmission.confirm_status.in_(list(SS.ALL_ACTIVE)),
        )
        .count()
    )

    return {
        "roles": roles,
        "canSubmit":        can_submit_to_project(context, project_id, db),
        "canConfirm":       can_confirm_submission_by_project(context, project_id, db),
        "canCoordinate":    can_coordinator_feedback_by_project(context, project_id, db),
        "canEscalateToCEO": can_escalate_to_ceo_by_project(context, project_id, db),
        "canCeoDecide":     can_ceo_decide_by_project(context, project_id, db),
        "canViewCenter":    can_access_confirmation_center(context),
        "pendingCount":     pending_count,
    }
