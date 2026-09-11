from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .. import models


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
