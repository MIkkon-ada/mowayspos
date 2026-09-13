from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .. import models
from ..domain.project_permissions import A_VIEW


PROJECT_ROLES = frozenset({"owner", "coordinator", "member", "project_ceo"})
RoleSource = Literal["project_members", "legacy_fields", "none"]


@dataclass(frozen=True)
class ProjectRoleResolution:
    roles: frozenset[str]
    source: RoleSource


def _split_legacy_names(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        value = "、".join(str(item or "") for item in value)
    normalized = str(value or "").strip()
    if not normalized:
        return ()
    return tuple(
        item.strip()
        for item in re.split(r"[,，、/；;\n]+", normalized)
        if item.strip()
    )


def _legacy_roles_for_name(project: models.Project, person_name: str) -> frozenset[str]:
    roles: set[str] = set()
    if person_name in _split_legacy_names(project.owners):
        roles.add("owner")
    if person_name in _split_legacy_names(project.coordinator):
        roles.add("coordinator")
    if person_name in _split_legacy_names(project.collaborators):
        roles.add("member")
    return frozenset(roles)


def resolve_project_roles(
    db,
    person_id: int | None,
    project_id: int | None,
    *,
    allow_legacy: bool = False,
) -> ProjectRoleResolution:
    """Resolve one person's project roles with explicit legacy fallback opt-in."""
    if person_id is None or project_id is None:
        return ProjectRoleResolution(frozenset(), "none")

    person = db.get(models.Person, person_id)
    project = db.get(models.Project, project_id)
    if person is None or project is None or not bool(person.is_active):
        return ProjectRoleResolution(frozenset(), "none")

    current_roles = frozenset(
        row.role
        for row in db.query(models.ProjectMember)
        .filter_by(project_id=project_id, person_id=person_id)
        .all()
        if row.role in PROJECT_ROLES
    )
    if current_roles:
        return ProjectRoleResolution(current_roles, "project_members")
    if not allow_legacy:
        return ProjectRoleResolution(frozenset(), "none")

    legacy_roles = _legacy_roles_for_name(project, person.name)
    if legacy_roles:
        return ProjectRoleResolution(legacy_roles, "legacy_fields")
    return ProjectRoleResolution(frozenset(), "none")


def authorize_project_view(current_user: str, project: models.Project, db, *, denial_detail: str | None = None):
    """Authorize historical project-field readers without extending write access."""
    from ..permissions import get_user_context_from_db
    from ..services.project_access import authorize_project_action_with_resolution

    context = get_user_context_from_db(current_user, db)
    resolution = resolve_project_roles(db, context.get("person_id"), project.id, allow_legacy=True)
    return authorize_project_action_with_resolution(
        current_user,
        project,
        A_VIEW,
        db,
        resolution=resolution,
        denial_detail=denial_detail,
    )


def resolve_visible_project_ids(context: dict, db) -> frozenset[int] | None:
    """Return current-member and historical-field project visibility for read lists."""
    from ..services.project_access import resolve_member_project_ids

    member_ids = resolve_member_project_ids(context, db)
    if member_ids is None:
        return None
    legacy_names = [
        str(name).strip()
        for name in context.get("visible_projects") or []
        if str(name).strip()
    ]
    legacy_ids = {
        int(row[0])
        for row in db.query(models.Project.id).filter(models.Project.name.in_(legacy_names)).all()
    } if legacy_names else set()
    return frozenset(member_ids | legacy_ids)
