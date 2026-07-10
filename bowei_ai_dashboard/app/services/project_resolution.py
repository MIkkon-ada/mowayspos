from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .. import models

_NAME_KEYS = ("special_project", "related_special_project", "project_name", "projectName")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _project_by_id(db: Session, project_id: int) -> models.Project | None:
    return db.get(models.Project, project_id)


def _project_by_name(db: Session, name: str) -> models.Project | None:
    name = name.strip()
    if not name:
        return None
    return db.query(models.Project).filter(models.Project.name == name).first()


def _coerce_json_payload(json_payload: Any) -> Any:
    if json_payload is None:
        return None
    if isinstance(json_payload, (dict, list)):
        return json_payload
    if hasattr(json_payload, "model_dump"):
        try:
            return json_payload.model_dump()
        except Exception:
            pass
    if isinstance(json_payload, str):
        raw = json_payload.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return json_payload


def _iter_json_hints(value: Any, path: str = "json_payload"):
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}"
            if key == "project_id":
                project_id = _to_int(item)
                if project_id is not None:
                    yield ("project_id", next_path, project_id)
            elif key in _NAME_KEYS:
                name = _text(item)
                if name:
                    yield ("name", next_path, name)
            yield from _iter_json_hints(item, next_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _iter_json_hints(item, f"{path}[{idx}]")


def _set_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def resolve_project_context(
    db: Session,
    *,
    project_id: int | None = None,
    special_project: str | None = None,
    related_special_project: str | None = None,
    project_name: str | None = None,
    projectName: str | None = None,
    json_payload: Any = None,
    parent_task_id: int | None = None,
    allow_parent_task_lookup: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    matched_by: list[str] = []
    project: models.Project | None = None
    source: str | None = None
    is_conflict = False

    def _bind_candidate(candidate: models.Project | None, candidate_source: str) -> None:
        nonlocal project, source, is_conflict
        if candidate is None:
            return
        if project is None:
            project = candidate
            source = candidate_source
            matched_by.append(candidate_source)
            return
        if candidate.id == project.id:
            if candidate_source not in matched_by:
                matched_by.append(candidate_source)
            return
        is_conflict = True
        _set_warning(
            warnings,
            f"conflict between {source or 'unknown'} and {candidate_source}",
        )

    if project_id is not None:
        project = _project_by_id(db, project_id)
        if project is None:
            _set_warning(warnings, f"project_id {project_id} not found")
        else:
            source = "project_id"
            matched_by.append("project_id")
        return {
            "project_id": project.id if project else None,
            "project_name": project.name if project else None,
            "source": source,
            "matched_by": matched_by,
            "is_valid": project is not None,
            "is_ambiguous": False,
            "is_conflict": False,
            "needs_manual_review": project is None,
            "warnings": warnings,
        }

    explicit_candidates = [
        ("special_project", special_project),
        ("related_special_project", related_special_project),
        ("project_name", project_name),
        ("projectName", projectName),
    ]
    for candidate_source, candidate_name in explicit_candidates:
        name = _text(candidate_name)
        if not name:
            continue
        candidate = _project_by_name(db, name)
        if candidate is None:
            _set_warning(warnings, f"{candidate_source}={name!r} not found")
            continue
        _bind_candidate(candidate, candidate_source)

    coerced = _coerce_json_payload(json_payload)
    if coerced is not None:
        for kind, candidate_source, value in _iter_json_hints(coerced):
            if kind == "project_id":
                candidate = _project_by_id(db, int(value))
            else:
                candidate = _project_by_name(db, str(value))
            if candidate is None:
                _set_warning(warnings, f"{candidate_source}={value!r} not found")
                continue
            _bind_candidate(candidate, candidate_source)

    if project is None and allow_parent_task_lookup and parent_task_id is not None:
        task = db.get(models.Task, parent_task_id)
        if task is None:
            _set_warning(warnings, f"parent_task_id {parent_task_id} not found")
        else:
            if task.project_id is not None:
                project = _project_by_id(db, task.project_id)
                if project is not None:
                    source = "parent_task_id"
                    matched_by.append("parent_task_id")
                else:
                    _set_warning(warnings, f"parent_task_id {parent_task_id} project_id {task.project_id} not found")
            elif task.special_project:
                candidate = _project_by_name(db, task.special_project)
                if candidate is not None:
                    project = candidate
                    source = "parent_task_id"
                    matched_by.append("parent_task_id")
                else:
                    _set_warning(warnings, f"parent_task_id {parent_task_id} special_project={task.special_project!r} not found")

    is_valid = project is not None
    needs_manual_review = is_conflict or not is_valid
    return {
        "project_id": project.id if project else None,
        "project_name": project.name if project else None,
        "source": source,
        "matched_by": matched_by,
        "is_valid": is_valid,
        "is_ambiguous": is_conflict or len(matched_by) > 1,
        "is_conflict": is_conflict,
        "needs_manual_review": needs_manual_review,
        "warnings": warnings,
    }


def resolve_project_id(
    db: Session,
    *,
    project_id: int | None = None,
    special_project: str | None = None,
    related_special_project: str | None = None,
    project_name: str | None = None,
    projectName: str | None = None,
    json_payload: Any = None,
    parent_task_id: int | None = None,
    allow_parent_task_lookup: bool = False,
) -> int | None:
    return resolve_project_context(
        db,
        project_id=project_id,
        special_project=special_project,
        related_special_project=related_special_project,
        project_name=project_name,
        projectName=projectName,
        json_payload=json_payload,
        parent_task_id=parent_task_id,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )["project_id"]
