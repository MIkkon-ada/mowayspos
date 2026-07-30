"""Frozen work-plan snapshots and deterministic meeting change validation."""

from __future__ import annotations

import math
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

WORKSTREAM_FIELDS = (
    "key_task",
    "owner",
    "coordinator",
    "collaborators",
    "plan_time",
    "status",
    "key_achievement",
    "completion_standard",
)

SUBTASK_FIELDS = (
    "title",
    "assignee",
    "plan_time",
    "completion_criteria",
    "status",
    "notes",
)


def build_meeting_plan_snapshot(project_id: int, db: Session) -> dict[str, Any]:
    """Freeze live, non-deleted work-plan rows without inferring meeting facts."""
    member_names: list[str] = []
    seen_member_names: set[str] = set()
    member_rows = (
        db.query(models.Person.name)
        .join(models.ProjectMember, models.ProjectMember.person_id == models.Person.id)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.Person.is_active.is_(True),
        )
        .order_by(models.Person.name, models.Person.id)
        .all()
    )
    for (name,) in member_rows:
        normalized_name = (name or "").strip()
        if normalized_name and normalized_name not in seen_member_names:
            member_names.append(normalized_name)
            seen_member_names.add(normalized_name)

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
    return {
        "project_id": project_id,
        "member_names": member_names,
        "workstreams": workstreams,
    }


def validate_meeting_change_proposal(
    raw: dict[str, Any],
    snapshot: dict[str, Any],
    transcript_text: str | None = None,
) -> dict[str, Any]:
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
    _validate_evidence_against_transcript(evidence, transcript_text, errors)
    reason = _normalize_reason(raw.get("reason"), errors)
    confidence = _normalize_confidence(raw.get("confidence"), errors)

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

    if action == "update_workstream":
        workstream_id = raw_target.get("workstream_id")
        if not _is_id(workstream_id):
            errors.append("update_workstream requires target.workstream_id")
        elif workstream_id not in workstreams:
            errors.append("target workstream_id is not present in snapshot")
        else:
            workstream = workstreams[workstream_id]
            target["workstream_id"] = workstream_id

    if action == "create_subtask":
        parent_workstream_id = raw_target.get("parent_workstream_id")
        if _is_id(parent_workstream_id):
            if parent_workstream_id not in workstreams:
                errors.append("target parent_workstream_id is not present in snapshot")
            else:
                workstream = workstreams[parent_workstream_id]
                target["parent_workstream_id"] = parent_workstream_id

    if action == "update_subtask":
        subtask_id = raw_target.get("subtask_id")
        if not _is_id(subtask_id) or subtask_id not in subtasks:
            errors.append("target subtask_id is not present in snapshot")
        else:
            workstream, subtask = subtasks[subtask_id]
            target["parent_workstream_id"] = workstream["id"]
            target["subtask_id"] = subtask_id
            supplied_parent_workstream_id = raw_target.get("parent_workstream_id")
            if (
                supplied_parent_workstream_id is not None
                and supplied_parent_workstream_id != workstream["id"]
            ):
                errors.append("target parent_workstream_id does not contain subtask_id")

    return workstream, subtask


def _allowed_fields_for_action(action: str) -> tuple[str, ...]:
    if action in {"create_workstream", "update_workstream"}:
        return WORKSTREAM_FIELDS
    if action in {"create_subtask", "update_subtask"}:
        return SUBTASK_FIELDS
    return ()


def _normalize_proposed(
    value: Any,
    allowed_fields: tuple[str, ...],
    errors: list[str],
) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append("proposed must be an object")
        return {}

    unsupported = sorted(str(key) for key in value if key not in allowed_fields)
    if unsupported:
        errors.append(f"proposed contains unsupported fields: {', '.join(unsupported)}")

    proposed: dict[str, str] = {}
    for key in allowed_fields:
        if key not in value:
            continue
        item = value[key]
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


def _validate_evidence_against_transcript(
    evidence: list[str],
    transcript_text: str | None,
    errors: list[str],
) -> None:
    if not isinstance(transcript_text, str) or not transcript_text.strip():
        errors.append("transcript_text must be a non-empty string")
        return
    if any(excerpt not in transcript_text for excerpt in evidence):
        errors.append("evidence excerpts must occur in transcript_text")


def _normalize_reason(value: Any, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append("reason must be a non-empty string")
        return ""
    return value.strip()


def _normalize_confidence(value: Any, errors: list[str]) -> float:
    if isinstance(value, bool):
        errors.append("confidence must be a finite number between 0 and 1")
        return 0.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        errors.append("confidence must be a finite number between 0 and 1")
        return 0.0
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        errors.append("confidence must be a finite number between 0 and 1")
        return 0.0
    return confidence


def _validate_creation_requirements(
    action: str,
    proposed: dict[str, str],
    target: dict[str, Any],
    errors: list[str],
) -> None:
    if action == "create_workstream" and not proposed.get("key_task"):
        errors.append("create_workstream requires proposed.key_task")
    if action == "create_subtask":
        if "parent_workstream_id" not in target:
            errors.append("create_subtask requires target.parent_workstream_id")
        if not proposed.get("title"):
            errors.append("create_subtask requires proposed.title")
    if action in {"update_workstream", "update_subtask"} and not proposed:
        errors.append("update proposal must include at least one allowed field")


def _before_from_snapshot(
    action: str,
    workstream: dict[str, Any] | None,
    subtask: dict[str, Any] | None,
) -> dict[str, str]:
    if action == "update_workstream" and workstream is not None:
        return {field: str(workstream.get(field) or "") for field in WORKSTREAM_FIELDS}
    if action == "update_subtask" and subtask is not None:
        return {field: str(subtask.get(field) or "") for field in SUBTASK_FIELDS}
    return {}


def _add_unknown_person_review_notes(
    action: str,
    proposed: dict[str, str],
    snapshot: dict[str, Any],
    review_notes: list[str],
) -> None:
    known_members = _known_member_names(snapshot)
    if action in {"create_workstream", "update_workstream"}:
        for field in ("owner", "coordinator", "collaborators"):
            unknown_names = [
                name for name in _split_people(proposed.get(field, "")) if name not in known_members
            ]
            if unknown_names:
                review_notes.append(
                    f"{field} requires review for nonmember or inactive names: {', '.join(unknown_names)}"
                )
    elif action in {"create_subtask", "update_subtask"}:
        assignee = proposed.get("assignee", "")
        if assignee and assignee not in known_members:
            review_notes.append(
                f"assignee requires review for nonmember or inactive names: {assignee}"
            )


def _known_member_names(snapshot: dict[str, Any]) -> set[str]:
    rows = snapshot.get("member_names")
    if not isinstance(rows, list):
        return set()
    return {name.strip() for name in rows if isinstance(name, str) and name.strip()}


def _split_people(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item.strip() for item in re.split(r"[,/，、;；]", value) if item.strip()]


def _is_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
