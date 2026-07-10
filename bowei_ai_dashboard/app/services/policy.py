"""
Submission-level permission policy.

All public functions are side-effect-free predicates.
Routers import from here instead of duplicating logic.
"""
from sqlalchemy.orm import Session

from .. import models
from ..permissions import (
    can_ceo_decide_by_project,
    can_confirm_submission_by_project,
    can_coordinator_feedback_by_project,
    can_escalate_to_ceo_by_project,
    can_view_submission_in_confirmation_by_project,
    get_all_project_roles,
)


# ── Project-ID resolution ──────────────────────────────────────

def project_id_of(row: models.UpdateSubmission) -> int | None:
    """Single authority: always returns row.project_id directly."""
    return row.project_id


# ── Role lookup ────────────────────────────────────────────────

def user_roles_in_project(
    context: dict,
    project_id: int | None,
    db: Session,
) -> set[str]:
    """
    Current user's roles in a project.
    Returns {"super_admin"} for tech_admin; empty set when no record found.
    """
    if context.get("is_tech_admin"):
        return {"super_admin"}

    person_id = context.get("person_id")
    if person_id and project_id:
        db_roles = get_all_project_roles(person_id, project_id, db)
        if db_roles:
            return set(db_roles)

    return set()


# ── Per-submission checks (handle project_id=NULL guard) ───────

def can_confirm(context: dict, row: models.UpdateSubmission, db: Session) -> bool:
    proj_id = project_id_of(row)
    if proj_id is None:
        return bool(context.get("is_tech_admin"))
    return can_confirm_submission_by_project(context, proj_id, db)


def can_coordinate(context: dict, row: models.UpdateSubmission, db: Session) -> bool:
    proj_id = project_id_of(row)
    if proj_id is None:
        return bool(context.get("is_tech_admin"))
    return can_coordinator_feedback_by_project(context, proj_id, db)


def can_escalate(context: dict, row: models.UpdateSubmission, db: Session) -> bool:
    proj_id = project_id_of(row)
    if proj_id is None:
        return bool(context.get("is_tech_admin"))
    return can_escalate_to_ceo_by_project(context, proj_id, db)


def can_ceo_decide(context: dict, row: models.UpdateSubmission, db: Session) -> bool:
    proj_id = project_id_of(row)
    if proj_id is None:
        return bool(context.get("is_tech_admin"))
    return can_ceo_decide_by_project(context, proj_id, db)


def can_view_in_center(
    context: dict, row: models.UpdateSubmission, db: Session
) -> bool:
    proj_id = project_id_of(row)
    return can_view_submission_in_confirmation_by_project(
        context, proj_id, row.submitter or "", db
    )


def role_allows_pending_view(
    context: dict,
    row: models.UpdateSubmission,
    db: Session,
    *,
    proj_id: int | None = None,
) -> bool:
    """
    Role-based visibility filter on top of base visibility.
    owner / super_admin → unrestricted;
    coordinator → only waiting-coordinator items;
    project_ceo → only waiting-CEO items;
    member / none → own submissions only.
    """
    if context.get("is_tech_admin"):
        return True
    if proj_id is None:
        proj_id = project_id_of(row)
    roles = user_roles_in_project(context, proj_id, db)
    if "owner" in roles or "super_admin" in roles:
        return True
    # Deferred import to avoid circular dependency with workflow
    from .workflow import submission_status
    from ..domain import submission_status as SS
    if "coordinator" in roles:
        return submission_status(row) in SS.WAITING_COORDINATOR_FEEDBACK
    if "project_ceo" in roles:
        return submission_status(row) in SS.WAITING_CEO_DECISION
    return (row.submitter or "") == context.get("name", "")


# ── Batch-mode helpers (eliminate N+1 in list endpoints) ──────

def preload_user_project_roles(context: dict, db) -> dict[int, set[str]]:
    """
    一次性加载当前用户的所有项目角色 {project_id: set[role]}。
    在行循环中替代 get_all_project_roles，消除 N+1 查询。
    """
    from sqlalchemy import text as _t
    person_id = context.get("person_id")
    result: dict[int, set[str]] = {}
    if person_id:
        rows = db.execute(
            _t("SELECT project_id, role FROM project_members WHERE person_id = :pid"),
            {"pid": person_id},
        ).fetchall()
        for proj_id, role in rows:
            result.setdefault(proj_id, set()).add(role)
    return result


def _cached_roles(project_id: int | None, cache: dict[int, set[str]]) -> set[str]:
    if project_id is None:
        return set()
    return cache.get(project_id, set())


def can_view_batch(
    context: dict,
    submitter: str | None,
    project_id: int | None,
    cache: dict[int, set[str]],
) -> bool:
    """无 DB 查询的行级可见性检查（配合 preload_user_project_roles 使用）。"""
    if context["can_view_all"]:
        return True
    if submitter == context.get("name", ""):
        return True
    if context.get("is_ceo"):
        return True
    if project_id is None:
        return False
    return bool(_cached_roles(project_id, cache) & {"owner", "coordinator", "project_ceo"})


def role_allows_batch(
    context: dict,
    submitter: str | None,
    project_id: int | None,
    raw_status: str | None,
    cache: dict[int, set[str]],
) -> bool:
    """无 DB 查询的角色过滤（配合 preload_user_project_roles 使用）。"""
    from ..domain import submission_status as SS
    if context.get("is_tech_admin"):
        return True
    if context.get("can_view_all"):
        return True
    roles = _cached_roles(project_id, cache)
    if "owner" in roles or "super_admin" in roles:
        return True
    norm = SS.normalize(raw_status)
    if "coordinator" in roles:
        return norm in SS.WAITING_COORDINATOR_FEEDBACK
    if "project_ceo" in roles:
        return norm in SS.WAITING_CEO_DECISION
    return (submitter or "") == context.get("name", "")


# ── Project-level capability checks (no row needed) ───────────

def can_confirm_for_project(
    context: dict, project_id: int, db: Session
) -> bool:
    return can_confirm_submission_by_project(context, project_id, db)


def can_coordinate_for_project(
    context: dict, project_id: int, db: Session
) -> bool:
    return can_coordinator_feedback_by_project(context, project_id, db)


def can_escalate_for_project(
    context: dict, project_id: int, db: Session
) -> bool:
    return can_escalate_to_ceo_by_project(context, project_id, db)


def can_ceo_decide_for_project(
    context: dict, project_id: int, db: Session
) -> bool:
    return can_ceo_decide_by_project(context, project_id, db)


def can_submit_to_project(
    context: dict, project_id: int, db: Session
) -> bool:
    """Can this user submit a progress update to the project?"""
    if context.get("is_tech_admin"):
        return True
    person_id = context.get("person_id")
    if person_id is not None:
        roles = get_all_project_roles(person_id, project_id, db)
        if roles:
            return any(r in ("owner", "member", "coordinator") for r in roles)
    return False
