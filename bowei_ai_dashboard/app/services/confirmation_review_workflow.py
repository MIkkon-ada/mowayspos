"""Shared identity, access, and state helpers for confirmation review workflows."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..domain.workflow_permissions import A_CONFIRMATION_REVIEW
from ..permissions import (
    can_access_confirmation_center,
    can_assign_submission,
    require_project_owner_or_admin,
)
from ..services import policy as P
from ..services import workflow as W
from ..services.project_close import require_project_business_writable
from ..services.project_resolution import resolve_project_context


def load_submission(db: Session, submission_id: int) -> models.UpdateSubmission:
    row = db.get(models.UpdateSubmission, submission_id)
    if not row:
        raise HTTPException(404, "confirmation not found")
    return row


def unique_active_person_id_for_name(db: Session, name: str) -> int | None:
    rows = (
        db.query(models.Person.id)
        .filter(models.Person.name == name, models.Person.is_active.is_(True))
        .limit(2)
        .all()
    )
    return rows[0][0] if len(rows) == 1 else None


def is_submission_submitter(
    row: models.UpdateSubmission,
    context: dict,
    current_user: str,
    db: Session,
) -> bool:
    """Use submitter_id for new rows; only legacy rows may match stored strings."""
    if row.submitter_id is not None:
        person_id = context.get("person_id")
        return person_id is not None and row.submitter_id == person_id

    submitter = (row.submitter or "").strip()
    current_user = (current_user or "").strip()
    if submitter and submitter == current_user:
        return True

    person_id = context.get("person_id")
    context_name = (context.get("name") or "").strip()
    return bool(
        submitter
        and person_id is not None
        and context_name
        and submitter == context_name
        and unique_active_person_id_for_name(db, context_name) == person_id
    )


def submission_recipient_id(
    row: models.UpdateSubmission,
    db: Session,
) -> int | None:
    """Resolve a submitter notification recipient without re-resolving new rows."""
    if row.submitter_id is not None:
        return row.submitter_id
    if not row.submitter:
        return None
    from ..services.notify import person_id_for_account

    return (
        person_id_for_account(row.submitter, db)
        or unique_active_person_id_for_name(db, row.submitter.strip())
    )


def submission_project_context(
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


def submission_project_id(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> int | None:
    return submission_project_context(
        db,
        row,
        json_payload=json_payload,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )["project_id"]


def submission_project_name(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> str:
    context = submission_project_context(
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


def resolve_pending_project_id(
    db: Session,
    project_id: int | None,
    special_project: str | None,
) -> int | None:
    if project_id is not None:
        return project_id
    if not special_project:
        return None
    return resolve_project_context(db, special_project=special_project)["project_id"]


def require_submission_project_access(
    row: models.UpdateSubmission,
    context: dict,
    db: Session | None = None,
) -> int | None:
    project_id = submission_project_id(db, row) if db is not None else P.project_id_of(row)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(422, "submission missing project_id")
    return project_id


def require_submission_writable(
    row: models.UpdateSubmission,
    context: dict,
    db: Session,
) -> int | None:
    """Confirmation writes validate project access before project lifecycle writability."""
    project_id = require_submission_project_access(row, context, db)
    require_project_business_writable(project_id, db)
    return project_id


def require_submission_owner_or_admin(
    row: models.UpdateSubmission,
    context: dict,
    current_user: str,
    db: Session,
) -> int | None:
    project_id = require_submission_project_access(row, context, db)
    if project_id is None:
        return None
    require_project_owner_or_admin(current_user, project_id, db)
    return project_id


def require_confirmation_center(context: dict) -> None:
    if context.get("is_tech_admin"):
        return
    if not can_access_confirmation_center(context):
        raise HTTPException(403, "permission denied")


def can_owner_style_action(
    context: dict,
    row: models.UpdateSubmission,
    db: Session,
    *,
    allow_assign: bool = False,
) -> bool:
    if context.get("is_tech_admin"):
        return True
    if P.decide_workflow_for_project(
        context,
        row.project_id,
        A_CONFIRMATION_REVIEW,
        db,
    ).allowed:
        return True
    if allow_assign and can_assign_submission(context):
        return True
    return False


def require_owner_style_actor(
    context: dict,
    row: models.UpdateSubmission,
    db: Session,
    *,
    allow_assign: bool = False,
) -> None:
    if context.get("is_tech_admin"):
        return
    if can_owner_style_action(context, row, db, allow_assign=allow_assign):
        return
    raise HTTPException(403, "permission denied")
