from __future__ import annotations

import re
from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app import models
from app.permissions import (
    get_all_project_roles,
    get_user_context_from_db,
    require_login,
    require_project_access,
)


_FIXED_TERMS = (
    "Moways",
    "关键任务",
    "重点工作",
    "成果入库",
    "企业教练",
    "项目统筹人",
)
_NAME_SEPARATOR = re.compile(r"[,，、]")
_MANAGEMENT_ROLES = {"owner", "coordinator"}


def _split_names(values: Iterable[str | None]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _NAME_SEPARATOR.split(value or ""):
            name = part.strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _bounded_lines(lines: Iterable[str], limit: int = 400) -> str:
    accepted: list[str] = []
    current_length = 0
    for line in lines:
        added_length = len(line) + (1 if accepted else 0)
        if current_length + added_length > limit:
            continue
        accepted.append(line)
        current_length += added_length
    return "\n".join(accepted)


def _unique_text(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _project_is_active(project: models.Project, db: Session) -> bool:
    if str(project.status or "").strip() == "active":
        return True

    lifecycle = str(getattr(project, "lifecycle_status", "") or "").strip()
    if lifecycle == "active":
        return True

    columns = {
        str(column["name"]).lower()
        for column in inspect(db.get_bind()).get_columns("projects")
    }
    if "lifecycle_status" not in columns:
        return False
    stored_lifecycle = db.execute(
        text("SELECT lifecycle_status FROM projects WHERE id=:project_id"),
        {"project_id": project.id},
    ).scalar()
    return str(stored_lifecycle or "").strip() == "active"


def _matches_assignment(
    *,
    person_id: int | None,
    display_name: str,
    assigned_person_id: int | None,
    assigned_name: str | None,
    allow_name_fallback: bool,
) -> bool:
    if assigned_person_id is not None:
        return person_id is not None and int(person_id) == int(assigned_person_id)
    return allow_name_fallback and display_name == str(assigned_name or "").strip()


def _legacy_name_maps_uniquely_to_person(
    *,
    project_id: int,
    person_id: int | None,
    display_name: str,
    db: Session,
) -> bool:
    if person_id is None or not display_name:
        return False
    matching_ids = {
        int(row[0])
        for row in (
            db.query(models.ProjectMember.person_id)
            .join(models.Person, models.Person.id == models.ProjectMember.person_id)
            .filter(
                models.ProjectMember.project_id == project_id,
                or_(
                    models.Person.name == display_name,
                    models.ProjectMember.person_name_snapshot == display_name,
                ),
            )
            .distinct()
            .all()
        )
    }
    return matching_ids == {int(person_id)}


def build_work_report_asr_context(
    current_user: str,
    project_id: int,
    selected_task_id: int,
    db: Session,
) -> str:
    username = require_login(current_user, db)
    require_project_access(username, project_id, db)

    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if not _project_is_active(project, db):
        raise HTTPException(status_code=409, detail="project_not_active")

    selected = (
        db.query(models.SubTask, models.Task)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(
            models.SubTask.id == selected_task_id,
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
        )
        .first()
    )
    if selected is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    selected_subtask, task = selected
    if task.project_id != project_id:
        raise HTTPException(status_code=403, detail="task_outside_project")

    identity = get_user_context_from_db(username, db)
    roles = set(
        get_all_project_roles(int(identity["person_id"]), project_id, db)
        if identity.get("person_id") is not None
        else []
    )
    is_manager = bool(identity.get("can_view_all")) or bool(
        roles & _MANAGEMENT_ROLES
    )
    display_name = str(identity.get("name") or "").strip()
    person_id = identity.get("person_id")
    allow_name_fallback = _legacy_name_maps_uniquely_to_person(
        project_id=project_id,
        person_id=person_id,
        display_name=display_name,
        db=db,
    )
    is_assigned = (
        _matches_assignment(
            person_id=person_id,
            display_name=display_name,
            assigned_person_id=task.owner_id,
            assigned_name=task.owner,
            allow_name_fallback=allow_name_fallback,
        )
        or _matches_assignment(
            person_id=person_id,
            display_name=display_name,
            assigned_person_id=selected_subtask.assignee_id,
            assigned_name=selected_subtask.assignee,
            allow_name_fallback=allow_name_fallback,
        )
    )
    if not is_manager and not is_assigned:
        raise HTTPException(status_code=403, detail="work_report_scope_denied")

    subtask_titles = _unique_text([selected_subtask.title])
    related_people = _split_names(
        [
            selected_subtask.assignee,
            task.owner,
            task.coordinator,
            task.collaborators,
        ]
    )
    lines = [
        f"当前关键任务：{'、'.join(subtask_titles)}",
        f"当前重点工作：{task.key_task}",
        f"当前项目：{project.name}",
        f"相关人员：{'、'.join(related_people)}",
        f"常用术语：{'、'.join(_FIXED_TERMS)}",
    ]
    return _bounded_lines(lines)
