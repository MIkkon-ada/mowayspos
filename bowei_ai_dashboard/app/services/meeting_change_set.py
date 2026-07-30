"""Frozen work-plan snapshots and deterministic meeting change validation."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .. import models


ALLOWED_ACTIONS = {
    "create_workstream",
    "update_workstream",
    "create_subtask",
    "update_subtask",
}

WORKSTREAM_FIELDS = {
    "key_task",
    "owner",
    "coordinator",
    "collaborators",
    "plan_time",
    "status",
    "key_achievement",
    "completion_standard",
}

SUBTASK_FIELDS = {
    "title",
    "assignee",
    "plan_time",
    "completion_criteria",
    "status",
    "notes",
}


def build_meeting_plan_snapshot(project_id: int, db: Session) -> dict[str, Any]:
    """Freeze live, non-deleted work-plan rows without inferring meeting facts."""
    workstreams: list[dict[str, Any]] = []
    rows = (
        db.query(models.Task)
        .filter_by(project_id=project_id, is_deleted=False)
        .order_by(models.Task.id)
        .all()
    )
    for task in rows:
        subtasks = (
            db.query(models.SubTask)
            .filter_by(task_id=task.id, is_deleted=False)
            .order_by(models.SubTask.id)
            .all()
        )
        workstreams.append(
            {
                "id": task.id,
                "key_task": task.key_task or "",
                "owner": task.owner or "",
                "coordinator": task.coordinator or "",
                "collaborators": task.collaborators or "",
                "plan_time": task.plan_time or "",
                "status": task.status or "",
                "key_achievement": task.key_achievement or "",
                "completion_standard": task.completion_standard or "",
                "subtasks": [
                    {
                        "id": subtask.id,
                        "title": subtask.title or "",
                        "assignee": subtask.assignee or "",
                        "plan_time": subtask.plan_time or "",
                        "completion_criteria": subtask.completion_criteria or "",
                        "status": subtask.status or "",
                        "notes": subtask.notes or "",
                    }
                    for subtask in subtasks
                ],
            }
        )
    return {"project_id": project_id, "workstreams": workstreams}


def validate_meeting_change_proposal(raw: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a safe, review-only proposal derived from one frozen plan snapshot."""
    raw = raw if isinstance(raw, dict) else {}
    snapshot_project_id = snapshot.get("project_id")
    action = str(raw.get("action") or "").strip()
    raw_target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    errors: list[str] = []
    review_notes: list[str] = []

    if action not in ALLOWED_ACTIONS:
        errors.append("action is not allowed")

    target: dict[str, Any] = {"project_id": snapshot_project_id}
    raw_project_id = raw_target.get("project_id")
    if raw_project_id is not None and raw_project_id != snapshot_project_id:
        errors.append("target project_id does not match snapshot")

    workstreams = _workstreams_by_id(snapshot)
    subtasks = _subtasks_by_id(workstreams)
    workstream, subtask = _resolve_target(
        action,
        raw_target,
        workstreams,
        subtasks,
        target,
        errors,
    )

    allowed_fields = _allowed_fields_for_action(action)
    proposed = _normalize_proposed(raw.get("proposed"), allowed_fields, errors)
    evidence = _normalize_evidence(raw.get("evidence"), errors)
    reason = _normalize_reason(raw.get("reason"), errors)
    confidence = _normalize_confidence(raw.get("confidence"))

    _validate_creation_requirements(action, proposed, target, errors)
    if not errors:
        _add_unknown_person_review_notes(action, proposed, snapshot, review_notes)

    before = _before_from_snapshot(action, workstream, subtask)
    validation = {
        "state": "blocked" if errors else "needs_review" if review_notes else "ready",
        "errors": errors or review_notes,
    }
    return {
        "action": action,
        "target": target,
        "before": before,
        "proposed": proposed,
        "evidence": evidence,
        "reason": reason,
        "confidence": confidence,
        "validation": validation,
    }


def _workstreams_by_id(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = snapshot.get("workstreams") if isinstance(snapshot.get("workstreams"), list) else []
    return {
        row["id"]: row
        for row in rows
        if isinstance(row, dict) and _is_id(row.get("id"))
    }


def _subtasks_by_id(workstreams: dict[int, dict[str, Any]]) -> dict[int, tuple[dict[str, Any], dict[str, Any]]]:
    result: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for workstream in workstreams.values():
        rows = workstream.get("subtasks") if isinstance(workstream.get("subtasks"), list) else []
        for subtask in rows:
            if isinstance(subtask, dict) and _is_id(subtask.get("id")):
                result[subtask["id"]] = (workstream, subtask)
    return result


def _resolve_target(
    action: str,
    raw_target: dict[str, Any],
    workstreams: dict[int, dict[str, Any]],
    subtasks: dict[int, tuple[dict[str, Any], dict[str, Any]]],
    target: dict[str, Any],
    errors: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    workstream: dict[str, Any] | None = None
    subtask: dict[str, Any] | None = None

    if action in {"update_workstream", "create_subtask"}:
        workstream_id = raw_target.get("workstream_id")
        if not _is_id(workstream_id):
            if action == "update_workstream":
                errors.append("update_workstream requires target.workstream_id")
        elif workstream_id not in workstreams:
            errors.append("target workstream_id is not present in snapshot")
        else:
            workstream = workstreams[workstream_id]
            target["workstream_id"] = workstream_id

    if action == "update_subtask":
        subtask_id = raw_target.get("subtask_id")
        if not _is_id(subtask_id) or subtask_id not in subtasks:
            errors.append("target subtask_id is not present in snapshot")
        else:
            workstream, subtask = subtasks[subtask_id]
            target["workstream_id"] = workstream["id"]
            target["subtask_id"] = subtask_id
            supplied_workstream_id = raw_target.get("workstream_id")
            if supplied_workstream_id is not None and supplied_workstream_id != workstream["id"]:
                errors.append("target workstream_id does not contain subtask_id")

    return workstream, subtask


def _allowed_fields_for_action(action: str) -> set[str]:
    if action in {"create_workstream", "update_workstream"}:
        return WORKSTREAM_FIELDS
    if action in {"create_subtask", "update_subtask"}:
        return SUBTASK_FIELDS
    return set()


def _normalize_proposed(value: Any, allowed_fields: set[str], errors: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append("proposed must be an object")
        return {}

    unsupported = sorted(str(key) for key in value if key not in allowed_fields)
    if unsupported:
        errors.append(f"proposed contains unsupported fields: {', '.join(unsupported)}")

    proposed: dict[str, str] = {}
    for key, item in value.items():
        if key not in allowed_fields:
            continue
        if not isinstance(item, str):
            errors.append(f"proposed.{key} must be a string")
            continue
        proposed[key] = item.strip()
    return proposed


def _normalize_evidence(value: Any, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append("evidence must contain at least one non-empty string")
        return []

    evidence: list[str] = []
    invalid_item = False
    for item in value:
        if not isinstance(item, str) or not item.strip():
            invalid_item = True
            continue
        evidence.append(item.strip())
    if not evidence:
        errors.append("evidence must contain at least one non-empty string")
    elif invalid_item:
        errors.append("evidence items must be non-empty strings")
    return evidence


def _normalize_reason(value: Any, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append("reason must be a non-empty string")
        return ""
    return value.strip()


def _normalize_confidence(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _validate_creation_requirements(
    action: str,
    proposed: dict[str, str],
    target: dict[str, Any],
    errors: list[str],
) -> None:
    if action == "create_workstream" and not proposed.get("key_task"):
        errors.append("create_workstream requires proposed.key_task")
    if action == "create_subtask":
        if "workstream_id" not in target:
            errors.append("create_subtask requires target.workstream_id")
        if not proposed.get("title"):
            errors.append("create_subtask requires proposed.title")


def _before_from_snapshot(
    action: str,
    workstream: dict[str, Any] | None,
    subtask: dict[str, Any] | None,
) -> dict[str, str]:
    if action == "update_workstream" and workstream is not None:
        return {field: str(workstream.get(field) or "") for field in sorted(WORKSTREAM_FIELDS)}
    if action == "update_subtask" and subtask is not None:
        return {field: str(subtask.get(field) or "") for field in sorted(SUBTASK_FIELDS)}
    return {}


def _add_unknown_person_review_notes(
    action: str,
    proposed: dict[str, str],
    snapshot: dict[str, Any],
    review_notes: list[str],
) -> None:
    field = "owner" if action in {"create_workstream", "update_workstream"} else "assignee"
    value = proposed.get(field, "")
    if value and value not in _known_people(snapshot):
        review_notes.append(f"{field} is not present in the frozen plan and requires review")


def _known_people(snapshot: dict[str, Any]) -> set[str]:
    people: set[str] = set()
    for workstream in _workstreams_by_id(snapshot).values():
        for field in ("owner", "coordinator", "collaborators"):
            people.update(_split_people(workstream.get(field)))
        for subtask in workstream.get("subtasks", []):
            if isinstance(subtask, dict):
                people.update(_split_people(subtask.get("assignee")))
    return people


def _split_people(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {item.strip() for item in re.split(r"[,/，、;；]", value) if item.strip()}


def _is_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
