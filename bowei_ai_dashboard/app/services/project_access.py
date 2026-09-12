from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import models
from ..api_errors import CodedHTTPException
from ..compatibility.project_roles import ProjectRoleResolution, resolve_project_roles
from ..domain.project_lifecycle import normalize as normalize_lifecycle
from ..domain.project_permissions import (
    ProjectPermissionResource,
    ProjectPermissionSubject,
    decide_project_action,
)
from ..permissions import get_user_context_from_db


@dataclass(frozen=True)
class ProjectAccessContext:
    context: dict
    subject: ProjectPermissionSubject
    resource: ProjectPermissionResource
    role_source: str


def _subject_from_context(context: dict, roles: frozenset[str]) -> ProjectPermissionSubject:
    return ProjectPermissionSubject(
        is_tech_admin=bool(context.get("is_tech_admin")),
        is_company_ceo=bool(context.get("is_ceo")),
        person_id=context.get("person_id"),
        project_roles=roles,
    )


def _raise_if_denied(decision, denial_detail: str | None = None) -> None:
    if decision.allowed:
        return
    raise CodedHTTPException(
        decision.status_code,
        decision.code,
        denial_detail if denial_detail is not None else decision.detail,
    )


def authorize_project_action_with_resolution(
    current_user: str,
    project: models.Project,
    action: str,
    db: Session,
    *,
    resolution: ProjectRoleResolution,
    requester_person_id: int | None = None,
    denial_detail: str | None = None,
) -> ProjectAccessContext:
    context = get_user_context_from_db(current_user, db)
    subject = _subject_from_context(context, resolution.roles)
    resource = ProjectPermissionResource(
        project_id=project.id,
        lifecycle=normalize_lifecycle(project.status),
        requester_person_id=requester_person_id,
    )
    decision = decide_project_action(subject, resource, action)
    _raise_if_denied(decision, denial_detail)
    return ProjectAccessContext(context, subject, resource, resolution.source)


def authorize_project_action(
    current_user: str,
    project: models.Project,
    action: str,
    db: Session,
    *,
    requester_person_id: int | None = None,
    denial_detail: str | None = None,
) -> ProjectAccessContext:
    """Authorize current member records without historical-field fallback."""
    context = get_user_context_from_db(current_user, db)
    resolution = resolve_project_roles(db, context.get("person_id"), project.id)
    return authorize_project_action_with_resolution(
        current_user,
        project,
        action,
        db,
        resolution=resolution,
        requester_person_id=requester_person_id,
        denial_detail=denial_detail,
    )


def authorize_global_project_action(
    current_user: str,
    action: str,
    db: Session,
) -> ProjectAccessContext:
    context = get_user_context_from_db(current_user, db)
    subject = _subject_from_context(context, frozenset())
    resource = ProjectPermissionResource()
    decision = decide_project_action(subject, resource, action)
    _raise_if_denied(decision)
    return ProjectAccessContext(context, subject, resource, "none")


def resolve_member_project_ids(
    context: dict,
    db: Session,
) -> frozenset[int] | None:
    """Resolve member-table list visibility without per-project role loads."""
    if context.get("can_view_all"):
        return None

    person_id = context.get("person_id")
    member_ids = {
        int(row[0])
        for row in (
            db.query(models.ProjectMember.project_id)
            .filter(models.ProjectMember.person_id == person_id)
            .distinct()
            .all()
        )
    } if person_id is not None else set()

    return frozenset(member_ids)
