from __future__ import annotations

import re
from collections.abc import Iterable

from fastapi import HTTPException
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


def build_work_report_asr_context(
    current_user: str,
    project_id: int,
    selected_task_id: int,
    db: Session,
) -> str:
    username = require_login(current_user, db)

    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if not project.is_active or project.status != "active":
        raise HTTPException(status_code=409, detail="project_not_active")

    require_project_access(username, project_id, db)

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
    is_assigned = (
        display_name == str(task.owner or "").strip()
        or display_name == str(selected_subtask.assignee or "").strip()
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
