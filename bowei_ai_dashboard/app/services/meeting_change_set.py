"""Frozen work-plan snapshots and deterministic meeting change validation."""

from __future__ import annotations

import math
import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models
from ..domain import task_status as TS
from ..permissions import PROJECT_ROLE_OWNER_KEY, require_project_role
from ..services.project_close import require_project_business_writable
from ..time_utils import utc_now


ALLOWED_ACTIONS = {
    "create_workstream",
    "update_workstream",
    "create_subtask",
    "update_subtask",
    "update_execution_schedule",
    "create_execution_schedule",
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

EXECUTION_SCHEDULE_FIELDS = (
    "plan_type",
    "plan_month",
    "title",
    "start_date",
    "due_date",
    "assignee",
    "assignee_id",
    "status",
    "expected_output",
    "completion_criteria",
    "progress_note",
    "risk_dependency",
    "actual_output",
    "delay_reason",
    "sort_order",
)

EXECUTION_SCHEDULE_FIELD_LIMITS = {
    "plan_type": 10,
    "plan_month": 7,
    "title": 200,
    "start_date": 10,
    "due_date": 10,
    "assignee": 50,
    "status": 20,
    "expected_output": 2000,
    "completion_criteria": 2000,
    "progress_note": 4000,
    "risk_dependency": 4000,
    "actual_output": 4000,
    "delay_reason": 2000,
}

EXECUTION_SCHEDULE_STATUS_VALUES = {
    TS.S_NOT_STARTED,
    TS.S_IN_PROGRESS,
    TS.S_COMPLETED,
    TS.S_DELAYED,
    TS.S_PAUSED,
    TS.S_ARCHIVED,
}

WORKSTREAM_FIELD_LIMITS = {
    "key_task": 200,
    "owner": 50,
    "coordinator": 50,
    "collaborators": 200,
    "plan_time": 20,
    "status": 20,
    "key_achievement": 200,
}

SUBTASK_FIELD_LIMITS = {
    "title": 200,
    "assignee": 50,
    "plan_time": 20,
    "status": 20,
}

ALLOWED_STATUS_VALUES = {
    TS.S_NOT_STARTED,
    TS.S_IN_PROGRESS,
    TS.S_COMPLETED,
    TS.S_DELAYED,
    TS.S_PAUSED,
    TS.S_ARCHIVED,
}


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


def _execution_schedule_snapshot(row: models.ExecutionSchedule) -> dict[str, Any]:
    return {
        "id": row.id,
        "subtask_id": row.subtask_id,
        "plan_type": row.plan_type or "",
        "plan_month": row.plan_month or "",
        "title": row.title or "",
        "start_date": row.start_date.isoformat() if row.start_date else "",
        "due_date": row.due_date.isoformat() if row.due_date else "",
        "assignee": row.assignee or "",
        "assignee_id": row.assignee_id,
        "status": row.status or "",
        "expected_output": row.expected_output or "",
        "completion_criteria": row.completion_criteria or "",
        "progress_note": row.progress_note or "",
        "risk_dependency": row.risk_dependency or "",
        "actual_output": row.actual_output or "",
        "delay_reason": row.delay_reason or "",
        "sort_order": row.sort_order or 0,
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
    if action in {"update_execution_schedule", "create_execution_schedule"}:
        return validate_execution_schedule_proposal(raw, snapshot, transcript_text)
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
    proposed = _normalize_proposed(
        raw.get("proposed"),
        allowed_fields,
        _field_limits_for_action(action),
        errors,
    )
    evidence = _normalize_evidence(raw.get("evidence"), errors)
    _validate_evidence_against_transcript(evidence, transcript_text, errors)
    reason = _normalize_reason(raw.get("reason"), errors)
    confidence = _normalize_confidence(raw.get("confidence"), errors)

    _validate_creation_requirements(action, proposed, target, errors)
    if not errors:
        _add_unknown_person_review_notes(action, proposed, snapshot, review_notes)
        errors.extend(review_notes)

    before = _before_from_snapshot(action, workstream, subtask)
    validation = {
        "state": "blocked" if errors else "ready",
        "errors": errors,
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


def validate_execution_schedule_proposal(
    raw: dict[str, Any],
    snapshot: dict[str, Any],
    document_text: str | None,
) -> dict[str, Any]:
    """Validate a schedule-only proposal against a frozen project snapshot."""
    raw = raw if isinstance(raw, dict) else {}
    action = str(raw.get("action") or "").strip()
    target_raw = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    errors: list[str] = []
    schedules: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    subtasks: dict[int, dict[str, Any]] = {}
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict):
            continue
        for subtask in workstream.get("subtasks", []) or []:
            if not isinstance(subtask, dict) or not _is_id(subtask.get("id")):
                continue
            subtasks[subtask["id"]] = workstream
            for schedule in subtask.get("execution_schedules", []) or []:
                if isinstance(schedule, dict) and _is_id(schedule.get("id")):
                    schedules[schedule["id"]] = (subtask, schedule)

    target: dict[str, Any] = {"project_id": snapshot.get("project_id")}
    before: dict[str, Any] = {}
    schedule: dict[str, Any] | None = None
    subtask: dict[str, Any] | None = None
    if action == "update_execution_schedule":
        schedule_id = target_raw.get("execution_schedule_id")
        if not _is_id(schedule_id):
            errors.append("update_execution_schedule requires target.execution_schedule_id")
        elif schedule_id not in schedules:
            errors.append("target execution_schedule_id is not present in snapshot")
        else:
            subtask, schedule = schedules[schedule_id]
            target.update({"execution_schedule_id": schedule_id, "subtask_id": subtask["id"]})
            before = {field: schedule.get(field) for field in EXECUTION_SCHEDULE_FIELDS}
    elif action == "create_execution_schedule":
        subtask_id = target_raw.get("subtask_id")
        if not _is_id(subtask_id) or subtask_id not in subtasks:
            errors.append("create_execution_schedule requires a valid target.subtask_id")
        else:
            subtask = next(
                item for workstream in snapshot.get("workstreams", [])
                if isinstance(workstream, dict)
                for item in workstream.get("subtasks", []) or []
                if isinstance(item, dict) and item.get("id") == subtask_id
            )
            target["subtask_id"] = subtask_id
    else:
        errors.append("action is not allowed")

    proposed_raw = raw.get("proposed") if isinstance(raw.get("proposed"), dict) else None
    if proposed_raw is None:
        errors.append("proposed must be an object")
        proposed_raw = {}
    unsupported = sorted(str(key) for key in proposed_raw if key not in EXECUTION_SCHEDULE_FIELDS)
    if unsupported:
        errors.append("proposed contains unsupported fields: " + ", ".join(unsupported))
    proposed: dict[str, Any] = {}
    for field in EXECUTION_SCHEDULE_FIELDS:
        if field not in proposed_raw:
            continue
        value = proposed_raw[field]
        if field in {"assignee_id", "sort_order"}:
            if field == "assignee_id" and value is not None and (not _is_id(value)):
                errors.append("proposed.assignee_id must be an integer or null")
                continue
            if field == "sort_order" and (isinstance(value, bool) or not isinstance(value, int)):
                errors.append("proposed.sort_order must be an integer")
                continue
            proposed[field] = value
            continue
        if not isinstance(value, str):
            errors.append(f"proposed.{field} must be a string")
            continue
        value = value.strip()
        limit = EXECUTION_SCHEDULE_FIELD_LIMITS.get(field)
        if limit and len(value) > limit:
            errors.append(f"proposed.{field} exceeds {limit} characters")
        if field in {"start_date", "due_date"} and value:
            try:
                from datetime import date
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"proposed.{field} must be YYYY-MM-DD")
        if field == "plan_type" and value not in {"week", "month"}:
            errors.append("proposed.plan_type must be week or month")
        if field == "status" and value not in EXECUTION_SCHEDULE_STATUS_VALUES:
            errors.append("proposed.status is not an allowed execution schedule status")
        proposed[field] = value
    if action == "update_execution_schedule" and not proposed:
        errors.append("update proposal must include at least one allowed field")
    if action == "create_execution_schedule":
        for required in ("plan_type", "title", "start_date", "due_date"):
            if not proposed.get(required):
                errors.append(f"create_execution_schedule requires proposed.{required}")

    evidence_raw = raw.get("evidence")
    evidence = [item.strip() for item in evidence_raw if isinstance(item, str) and item.strip()] if isinstance(evidence_raw, list) else []
    if not evidence:
        errors.append("evidence must contain at least one non-empty string")
    if not isinstance(document_text, str) or not document_text.strip():
        errors.append("document_text must be a non-empty string")
    elif any(item not in document_text for item in evidence):
        errors.append("evidence excerpts must occur in document_text")
    reason = raw.get("reason") if isinstance(raw.get("reason"), str) else ""
    if not reason.strip():
        errors.append("reason must be a non-empty string")
        reason = ""
    else:
        reason = reason.strip()
    confidence = _normalize_confidence(raw.get("confidence"), errors)
    return {
        "action": action,
        "target": target,
        "before": before,
        "proposed": proposed,
        "evidence": evidence,
        "reason": reason,
        "confidence": confidence,
        "validation": {"state": "blocked" if errors else "ready", "errors": errors},
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
    field_limits: dict[str, int],
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
        normalized = item.strip()
        max_length = field_limits.get(key)
        if max_length is not None and len(normalized) > max_length:
            errors.append(f"proposed.{key} exceeds {max_length} characters")
        if key == "status":
            canonical_status = TS.normalize(normalized)
            if canonical_status not in ALLOWED_STATUS_VALUES:
                errors.append("proposed.status is not an allowed task status")
            else:
                normalized = canonical_status
        proposed[key] = normalized
    return proposed


def _field_limits_for_action(action: str) -> dict[str, int]:
    if action in {"create_workstream", "update_workstream"}:
        return WORKSTREAM_FIELD_LIMITS
    if action in {"create_subtask", "update_subtask"}:
        return SUBTASK_FIELD_LIMITS
    return {}


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


class _ProjectMeetingLineageConflict(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


_MISSING_OWNER_VALUE = {"state": "missing"}


def _project_meeting_lineage(proposal: models.MeetingChangeProposal) -> dict[str, Any] | None:
    lineage = _json_object(proposal.lineage_json)
    return lineage if lineage else None


def _project_meeting_run(
    meeting: models.Meeting,
    change_set: models.MeetingChangeSet,
    db: Session,
) -> models.ProjectMeetingRun:
    if not meeting.document_source_id:
        raise _ProjectMeetingLineageConflict("missing project meeting document source")
    run = (
        db.query(models.ProjectMeetingRun)
        .filter(
            models.ProjectMeetingRun.project_id == change_set.project_id,
            models.ProjectMeetingRun.document_source_id == meeting.document_source_id,
        )
        .order_by(models.ProjectMeetingRun.id.desc())
        .first()
    )
    if not run:
        raise _ProjectMeetingLineageConflict("missing immutable project meeting run")
    return run


def _snapshot_project_objects(snapshot: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[int, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]]:
    workstreams: dict[int, dict[str, Any]] = {}
    key_tasks: dict[int, dict[str, Any]] = {}
    schedules: dict[int, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict) or not _is_id(workstream.get("id")):
            continue
        workstreams[workstream["id"]] = workstream
        for key_task in workstream.get("key_tasks", []):
            if not isinstance(key_task, dict) or not _is_id(key_task.get("id")):
                continue
            key_tasks[key_task["id"]] = key_task
            for schedule in key_task.get("execution_schedules", []):
                if isinstance(schedule, dict) and _is_id(schedule.get("id")):
                    schedules[schedule["id"]] = (workstream, key_task, schedule)
    return workstreams, key_tasks, schedules


def _schedule_live_value(row: models.ExecutionSchedule, field: str) -> Any:
    value = getattr(row, field, None)
    return value.isoformat() if hasattr(value, "isoformat") else value


def _analysis_item(result: dict[str, Any], name: str, identifier: str, value: Any) -> dict[str, Any] | None:
    rows = result.get(name)
    if not isinstance(rows, list):
        return None
    return next((item for item in rows if isinstance(item, dict) and item.get(identifier) == value), None)


def _snapshot_source_value(
    source: dict[str, Any],
    *,
    workstreams: dict[int, dict[str, Any]],
    key_tasks: dict[int, dict[str, Any]],
    schedules: dict[int, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> tuple[bool, Any]:
    source_object = source.get("source_object")
    source_field = source.get("source_field")
    if not isinstance(source_object, str) or not isinstance(source_field, str):
        return False, None
    try:
        object_type, raw_id = source_object.split(":", 1)
        object_id = int(raw_id)
    except (ValueError, TypeError):
        return False, None
    if object_type == "execution_schedule" and object_id in schedules:
        value = schedules[object_id][2]
    elif object_type == "key_task" and object_id in key_tasks:
        value = key_tasks[object_id]
    elif object_type == "workstream" and object_id in workstreams:
        value = workstreams[object_id]
    else:
        return False, None
    return source_field in value, value.get(source_field)


def _require_lineage(condition: bool, reason: str) -> None:
    if not condition:
        raise _ProjectMeetingLineageConflict(reason)


def _validate_owner_edit_history(
    *,
    field: str,
    value: Any,
    history: list[Any],
) -> None:
    events = [item for item in history if isinstance(item, dict) and item.get("field") == field]
    _require_lineage(bool(events), f"human edit for {field} has no owner edit history")
    event = events[-1]
    _require_lineage(
        event.get("after") == value
        and _is_id(event.get("editor_person_id"))
        and isinstance(event.get("edited_at"), str)
        and bool(event["edited_at"].strip()),
        f"human edit history for {field} is invalid",
    )


def _validate_project_meeting_lineage(
    *,
    proposal: models.MeetingChangeProposal,
    change_set: models.MeetingChangeSet,
    meeting: models.Meeting,
    db: Session,
) -> None:
    lineage = _project_meeting_lineage(proposal)
    _require_lineage(lineage is not None, "missing proposal lineage")
    run = _project_meeting_run(meeting, change_set, db)
    result = _json_object(run.result_json)
    snapshot = _json_object(run.snapshot_json)
    _require_lineage(result == _json_object(change_set.result_json), "immutable result does not match change set")
    _require_lineage(snapshot == _json_object(change_set.snapshot_json), "frozen snapshot does not match change set")
    _require_lineage(lineage.get("schema_version") == 1, "unsupported lineage schema")
    _require_lineage(lineage.get("action") == proposal.action, "lineage action does not match proposal")
    _require_lineage(lineage.get("requires_confirmation") is True, "proposal is missing confirmation requirement")

    fact_id = lineage.get("source_fact_id")
    match_id = lineage.get("source_match_id")
    delta_id = lineage.get("source_delta_id")
    change_id = lineage.get("change_id")
    fact = _analysis_item(result, "meeting_facts", "fact_id", fact_id)
    match = _analysis_item(result, "project_matches", "match_id", match_id)
    delta = _analysis_item(result, "project_deltas", "delta_id", delta_id)
    change = _analysis_item(result, "proposed_changes", "change_id", change_id)
    _require_lineage(all((fact, match, delta, change)), "lineage IDs are not present in immutable result")
    _require_lineage(match.get("fact_id") == fact_id, "match is not bound to lineage fact")
    _require_lineage(delta.get("source_fact_id") == fact_id and delta.get("source_match_id") == match_id, "delta is not bound to lineage match")
    _require_lineage(
        change.get("source_fact_id") == fact_id
        and change.get("source_match_id") == match_id
        and change.get("source_delta_id") == delta_id,
        "change is not bound to lineage chain",
    )
    target = change.get("target") if isinstance(change.get("target"), dict) else {}
    _require_lineage(target == lineage.get("target"), "lineage target does not match immutable change")
    _require_lineage(change.get("action") == proposal.action, "proposal action does not match immutable change")
    _require_lineage(change.get("requires_confirmation") is True, "immutable change is not confirmation-only")

    proposed = _json_object(proposal.proposed_json)
    original_proposed = change.get("proposed") if isinstance(change.get("proposed"), dict) else {}
    original_sources = change.get("field_sources") if isinstance(change.get("field_sources"), dict) else {}
    field_sources = lineage.get("field_sources") if isinstance(lineage.get("field_sources"), dict) else {}
    history = lineage.get("owner_edit_history") if isinstance(lineage.get("owner_edit_history"), list) else []
    _require_lineage(bool(proposed) and set(proposed) == set(field_sources), "proposal fields and lineage sources differ")
    _require_lineage(set(proposed).issubset(EXECUTION_SCHEDULE_FIELDS), "proposal contains a non-writable schedule field")
    fact_fields = fact.get("fields") if isinstance(fact.get("fields"), dict) else {}
    workstreams, key_tasks, schedules = _snapshot_project_objects(snapshot)
    for field, value in proposed.items():
        source = field_sources.get(field)
        _require_lineage(isinstance(source, dict), f"missing field source for {field}")
        source_type = source.get("source_type")
        if source_type == "human_edit":
            _require_lineage(source == {"source_type": "human_edit", "usage": "override"}, f"invalid human edit source for {field}")
            _validate_owner_edit_history(field=field, value=value, history=history)
            continue
        _require_lineage(value == original_proposed.get(field), f"non-human field {field} changed from immutable result")
        _require_lineage(source == original_sources.get(field), f"non-human field source for {field} changed")
        if source_type == "meeting_fact":
            _require_lineage(source.get("source_fact_id") == fact_id and field in fact_fields, f"meeting source for {field} is invalid")
            evidence = fact_fields[field].get("evidence") if isinstance(fact_fields[field], dict) else None
            _require_lineage(isinstance(evidence, list) and bool(evidence), f"meeting source for {field} has no field evidence")
            _require_lineage(lineage.get("meeting_evidence", {}).get(field) == evidence, f"lineage meeting evidence for {field} differs from fact")
        elif source_type == "project_baseline":
            valid_source, baseline_value = _snapshot_source_value(
                source,
                workstreams=workstreams,
                key_tasks=key_tasks,
                schedules=schedules,
            )
            _require_lineage(valid_source and baseline_value == value, f"baseline source for {field} is invalid")
        else:
            _require_lineage(False, f"unsupported field source for {field}")

    _require_lineage(target.get("project_id") == change_set.project_id, "target project boundary is invalid")
    _require_lineage(target.get("workstream_id") in workstreams and target.get("key_task_id") in key_tasks, "target is outside frozen snapshot")
    key_task = key_tasks[target["key_task_id"]]
    _require_lineage(any(item.get("id") == target["key_task_id"] for item in workstreams[target["workstream_id"]].get("key_tasks", []) if isinstance(item, dict)), "target hierarchy is invalid")
    _require_lineage(match.get("workstream_id") == target.get("workstream_id") and match.get("key_task_id") == target.get("key_task_id"), "match target hierarchy differs from change")
    _require_lineage(lineage.get("project_evidence") == match.get("project_evidence", []), "lineage project evidence differs from match")
    _require_lineage(lineage.get("delta") == delta, "lineage delta differs from immutable result")

    if proposal.action == "update_execution_schedule":
        schedule_id = target.get("execution_schedule_id")
        _require_lineage(proposal.target_id == schedule_id and schedule_id in schedules, "update target is outside frozen schedule snapshot")
        _, _, frozen_schedule = schedules[schedule_id]
        before_baseline = lineage.get("before_baseline") if isinstance(lineage.get("before_baseline"), dict) else {}
        proposal_before = _json_object(proposal.before_json)
        _require_lineage(lineage.get("baseline_state") == "existing_target", "update baseline state is invalid")
        _require_lineage(
            all(
                field in proposal_before
                and field in before_baseline
                and field in frozen_schedule
                and proposal_before[field] == before_baseline[field] == frozen_schedule[field]
                for field in proposed
            ),
            "update proposal baseline is not the frozen target baseline",
        )
        row = db.query(models.ExecutionSchedule).filter_by(id=schedule_id).with_for_update().first()
        live_key_task = db.get(models.SubTask, row.subtask_id) if row else None
        live_workstream = db.get(models.Task, live_key_task.task_id) if live_key_task else None
        _require_lineage(
            row is not None and not row.is_deleted and live_key_task is not None and not live_key_task.is_deleted
            and live_workstream is not None and not live_workstream.is_deleted and live_workstream.project_id == change_set.project_id
            and live_key_task.id == target["key_task_id"] and live_workstream.id == target["workstream_id"],
            "update live target identity changed",
        )
        _require_lineage(
            all(_schedule_live_value(row, field) == before_baseline[field] for field in proposed),
            "update touched field changed after analysis",
        )
    elif proposal.action == "create_execution_schedule":
        _require_lineage(proposal.target_id is None and lineage.get("baseline_state") == "not_applicable_new_object", "create baseline state is invalid")
        _require_lineage(not lineage.get("before_baseline"), "create proposal must not have target baseline")
        _require_lineage(
            proposal.parent_subtask_id == target.get("key_task_id"),
            "create proposal parent differs from lineage target",
        )
        parent = lineage.get("parent_baseline") if isinstance(lineage.get("parent_baseline"), dict) else {}
        _require_lineage(
            parent.get("project_id") == change_set.project_id and parent.get("workstream_id") == target.get("workstream_id") and parent.get("key_task_id") == target.get("key_task_id"),
            "create parent baseline is invalid",
        )
        live_key_task = (
            db.query(models.SubTask)
            .filter(models.SubTask.id == target["key_task_id"])
            .with_for_update()
            .first()
        )
        live_workstream = db.get(models.Task, live_key_task.task_id) if live_key_task else None
        baseline_key_task = parent.get("key_task") if isinstance(parent.get("key_task"), dict) else {}
        _require_lineage(
            live_key_task is not None and not live_key_task.is_deleted and live_workstream is not None and not live_workstream.is_deleted
            and live_workstream.id == target["workstream_id"] and live_workstream.project_id == change_set.project_id
            and live_key_task.status == baseline_key_task.get("status") and live_key_task.title == baseline_key_task.get("title"),
            "create parent changed after analysis",
        )
        title = " ".join(str(proposed.get("title") or "").split()).casefold()
        plan_type = proposed.get("plan_type")
        plan_month = proposed.get("plan_month")
        duplicate = (
            db.query(models.ExecutionSchedule)
            .filter_by(subtask_id=live_key_task.id, is_deleted=False)
            .with_for_update()
            .all()
        )
        _require_lineage(
            not any(
                " ".join((row.title or "").split()).casefold() == title
                and row.plan_type == plan_type and row.plan_month == plan_month
                for row in duplicate
            ),
            "create duplicate execution schedule detected",
        )
    else:
        raise _ProjectMeetingLineageConflict("lineage proposal action is not executable")


def _mark_project_meeting_conflicts(
    conflicts: list[tuple[models.MeetingChangeProposal, str]],
    db: Session,
) -> None:
    for proposal, reason in conflicts:
        proposal.execution_status = "conflict"
        proposal.validation_json = _json_dump({"state": "blocked", "errors": [reason]})
    db.commit()


def edit_project_meeting_lineage_proposal(
    *,
    proposal: models.MeetingChangeProposal,
    change_set: models.MeetingChangeSet,
    meeting: models.Meeting,
    actor: str,
    proposed_updates: dict[str, Any],
    db: Session,
) -> models.MeetingChangeProposal:
    if proposal.execution_status != "pending":
        raise HTTPException(409, "executed proposal cannot be edited")
    lineage = _project_meeting_lineage(proposal)
    if lineage is None:
        raise HTTPException(409, "proposal does not have project meeting lineage")
    if not isinstance(proposed_updates, dict) or not proposed_updates:
        raise HTTPException(422, "proposed must contain at least one field")
    unsupported = sorted(str(field) for field in proposed_updates if field not in EXECUTION_SCHEDULE_FIELDS)
    if unsupported:
        raise HTTPException(422, "proposed contains unsupported fields: " + ", ".join(unsupported))
    run = _project_meeting_run(meeting, change_set, db)
    snapshot = _json_object(run.snapshot_json)
    target = lineage.get("target") if isinstance(lineage.get("target"), dict) else {}
    _, _, schedules = _snapshot_project_objects(snapshot)
    current = _json_object(proposal.proposed_json)
    before = _json_object(proposal.before_json)
    sources = lineage.get("field_sources") if isinstance(lineage.get("field_sources"), dict) else {}
    history = lineage.get("owner_edit_history") if isinstance(lineage.get("owner_edit_history"), list) else []
    account = db.query(models.Account).filter_by(username=actor).first()
    if not account or not _is_id(account.person_id):
        raise HTTPException(403, "owner account is not linked to a person")
    for field, value in proposed_updates.items():
        if field in {"start_date", "due_date"} and value:
            try:
                from datetime import date
                date.fromisoformat(value)
            except (TypeError, ValueError):
                raise HTTPException(422, f"proposed.{field} must be YYYY-MM-DD")
        if lineage.get("baseline_state") == "existing_target" and field not in before:
            schedule = schedules.get(target.get("execution_schedule_id"))
            if schedule is None or field not in schedule[2]:
                raise HTTPException(409, f"frozen baseline is missing {field}")
            before[field] = schedule[2][field]
            baseline = lineage.get("before_baseline") if isinstance(lineage.get("before_baseline"), dict) else {}
            baseline[field] = schedule[2][field]
            lineage["before_baseline"] = baseline
        old = current.get(field, _MISSING_OWNER_VALUE)
        if old == value:
            continue
        current[field] = value
        sources[field] = {"source_type": "human_edit", "usage": "override"}
        history.append({
            "field": field,
            "before": old,
            "after": value,
            "editor_person_id": account.person_id,
            "edited_at": utc_now().isoformat(),
        })
    lineage["field_sources"] = sources
    lineage["owner_edit_history"] = history
    proposal.proposed_json = _json_dump(current)
    proposal.before_json = _json_dump(before)
    proposal.lineage_json = _json_dump(lineage)
    db.flush()
    return proposal


def edit_meeting_change_proposal(
    *,
    proposal: models.MeetingChangeProposal,
    change_set: models.MeetingChangeSet,
    transcript_text: str,
    proposed: dict[str, Any],
    evidence: list[str],
    reason: str,
    db: Session,
) -> models.MeetingChangeProposal:
    if proposal.execution_status != "pending":
        raise HTTPException(409, "executed proposal cannot be edited")
    snapshot = _json_object(change_set.snapshot_json)
    raw = _stored_proposal_raw(proposal, change_set.project_id)
    raw.update(
        {
            "proposed": proposed,
            "evidence": evidence,
            "reason": reason,
        }
    )
    normalized = validate_meeting_change_proposal(raw, snapshot, transcript_text)
    proposal.proposed_json = _json_dump(normalized["proposed"])
    proposal.evidence_json = _json_dump(normalized["evidence"])
    proposal.reason = normalized["reason"]
    proposal.validation_json = _json_dump(normalized["validation"])
    db.flush()
    return proposal


def execute_meeting_change_set(
    *,
    meeting: models.Meeting,
    proposal_ids: list[int],
    actor: str,
    db: Session,
) -> list[models.MeetingChangeProposal]:
    change_set = (
        db.query(models.MeetingChangeSet)
        .filter_by(meeting_id=meeting.id)
        .first()
    )
    if not change_set:
        raise HTTPException(404, "meeting change set not found")
    if not proposal_ids:
        return []

    require_project_role(
        actor,
        change_set.project_id,
        [PROJECT_ROLE_OWNER_KEY],
        db,
    )
    require_project_business_writable(change_set.project_id, db)

    unique_ids = list(dict.fromkeys(proposal_ids))
    if len(unique_ids) != len(proposal_ids):
        raise HTTPException(422, "proposal_ids must be unique")
    rows = (
        db.query(models.MeetingChangeProposal)
        .filter(
            models.MeetingChangeProposal.change_set_id == change_set.id,
            models.MeetingChangeProposal.id.in_(unique_ids),
        )
        .all()
    )
    if len(rows) != len(unique_ids):
        raise HTTPException(409, "selected proposal does not belong to meeting change set")
    by_id = {row.id: row for row in rows}
    proposals = [by_id[row_id] for row_id in unique_ids]

    snapshot = _json_object(change_set.snapshot_json)
    lineage_conflicts: list[tuple[models.MeetingChangeProposal, str]] = []
    for proposal in proposals:
        if proposal.execution_status != "pending":
            raise HTTPException(409, "selected proposal is not pending")
        validation = _json_object(proposal.validation_json)
        if validation.get("state") == "blocked":
            raise HTTPException(409, "blocked proposal cannot be executed")
        if _project_meeting_lineage(proposal) is not None:
            try:
                _validate_project_meeting_lineage(
                    proposal=proposal,
                    change_set=change_set,
                    meeting=meeting,
                    db=db,
                )
            except _ProjectMeetingLineageConflict as error:
                lineage_conflicts.append((proposal, error.reason))
            continue
        normalized = validate_meeting_change_proposal(
            _stored_proposal_raw(proposal, change_set.project_id),
            snapshot,
            meeting.transcript_text or "",
        )
        if normalized["validation"]["state"] == "blocked":
            raise HTTPException(409, "selected proposal failed revalidation")
        _require_live_target_matches_snapshot(
            proposal,
            change_set.project_id,
            db,
        )
    if lineage_conflicts:
        _mark_project_meeting_conflicts(lineage_conflicts, db)
        raise HTTPException(409, "project meeting proposal conflict")

    claimed_count = (
        db.query(models.MeetingChangeProposal)
        .filter(
            models.MeetingChangeProposal.change_set_id == change_set.id,
            models.MeetingChangeProposal.id.in_(unique_ids),
            models.MeetingChangeProposal.execution_status == "pending",
        )
        .update(
            {models.MeetingChangeProposal.execution_status: "executing"},
            synchronize_session=False,
        )
    )
    if claimed_count != len(proposals):
        raise HTTPException(409, "selected proposal was claimed by another execution")
    for proposal in proposals:
        proposal.execution_status = "executing"

    account = db.query(models.Account).filter_by(username=actor).first()
    for proposal in proposals:
        target = _apply_validated_proposal(
            proposal,
            change_set.project_id,
            actor,
            db,
        )
        proposal.result_target_id = target.id
        proposal.execution_status = "executed"
        proposal.executed_by_person_id = account.person_id if account else None
        proposal.executed_at = utc_now()
    change_set.status = "executed"
    db.flush()
    return proposals


def _stored_proposal_raw(
    proposal: models.MeetingChangeProposal,
    project_id: int,
) -> dict[str, Any]:
    target: dict[str, Any] = {"project_id": project_id}
    if proposal.target_type == "workstream" and proposal.target_id is not None:
        target["workstream_id"] = proposal.target_id
    if proposal.target_type == "subtask" and proposal.target_id is not None:
        target["subtask_id"] = proposal.target_id
    if proposal.target_type == "execution_schedule" and proposal.target_id is not None:
        target["execution_schedule_id"] = proposal.target_id
    if proposal.parent_workstream_id is not None:
        target["parent_workstream_id"] = proposal.parent_workstream_id
    return {
        "action": proposal.action,
        "target": target,
        "proposed": _json_object(proposal.proposed_json),
        "evidence": _json_list(proposal.evidence_json),
        "reason": proposal.reason,
        "confidence": proposal.confidence,
    }


def _require_live_target_matches_snapshot(
    proposal: models.MeetingChangeProposal,
    project_id: int,
    db: Session,
) -> None:
    before = _json_object(proposal.before_json)
    if proposal.action == "update_workstream":
        row = (
            db.query(models.Task)
            .filter(models.Task.id == proposal.target_id)
            .with_for_update()
            .first()
        )
        if not row or row.project_id != project_id or bool(row.is_deleted):
            raise HTTPException(409, "workstream target is stale or deleted")
        live = {field: str(getattr(row, field, "") or "") for field in WORKSTREAM_FIELDS}
        if live != before:
            raise HTTPException(409, "workstream target changed after analysis")
        return
    if proposal.action == "update_subtask":
        row = (
            db.query(models.SubTask)
            .filter(models.SubTask.id == proposal.target_id)
            .with_for_update()
            .first()
        )
        parent = (
            db.query(models.Task)
            .filter(models.Task.id == row.task_id)
            .with_for_update()
            .first()
            if row
            else None
        )
        if (
            not row
            or bool(row.is_deleted)
            or not parent
            or bool(parent.is_deleted)
            or parent.project_id != project_id
            or parent.id != proposal.parent_workstream_id
        ):
            raise HTTPException(409, "subtask target is stale or deleted")
        live = {field: str(getattr(row, field, "") or "") for field in SUBTASK_FIELDS}
        if live != before:
            raise HTTPException(409, "subtask target changed after analysis")
        return
    if proposal.action == "create_subtask":
        parent = (
            db.query(models.Task)
            .filter(models.Task.id == proposal.parent_workstream_id)
            .with_for_update()
            .first()
        )
        if not parent or bool(parent.is_deleted) or parent.project_id != project_id:
            raise HTTPException(409, "parent workstream is stale or deleted")
        return
    if proposal.action == "update_execution_schedule":
        row = (
            db.query(models.ExecutionSchedule)
            .filter(models.ExecutionSchedule.id == proposal.target_id)
            .with_for_update()
            .first()
        )
        subtask = db.get(models.SubTask, row.subtask_id) if row else None
        task = db.get(models.Task, subtask.task_id) if subtask else None
        if not row or row.is_deleted or not subtask or subtask.is_deleted or not task or task.is_deleted or task.project_id != project_id:
            raise HTTPException(409, "execution schedule target is stale or deleted")
        live = _execution_schedule_snapshot(row)
        current = {field: live.get(field) for field in EXECUTION_SCHEDULE_FIELDS}
        if current != before:
            raise HTTPException(409, "execution schedule target changed after analysis")
        return
    if proposal.action == "create_execution_schedule":
        subtask = db.get(models.SubTask, proposal.parent_workstream_id)
        task = db.get(models.Task, subtask.task_id) if subtask else None
        if not subtask or subtask.is_deleted or not task or task.is_deleted or task.project_id != project_id:
            raise HTTPException(409, "key task is stale or deleted")


def _apply_validated_proposal(
    proposal: models.MeetingChangeProposal,
    project_id: int,
    actor: str,
    db: Session,
) -> models.Task | models.SubTask | models.ExecutionSchedule:
    proposed = _json_object(proposal.proposed_json)
    if proposal.action in {"create_workstream", "update_workstream", "create_subtask", "update_subtask"} and "status" in proposed:
        canonical_status = TS.normalize(proposed["status"])
        if canonical_status not in ALLOWED_STATUS_VALUES:
            raise HTTPException(409, "proposal status is not canonical")
        proposed["status"] = canonical_status
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(409, "project no longer exists")

    if proposal.action == "create_workstream":
        values = {field: proposed.get(field, "") for field in WORKSTREAM_FIELDS}
        values["status"] = TS.normalize(values.get("status"))
        row = models.Task(
            project_id=project_id,
            special_project=project.name or "",
            source_type="meeting_change_set",
            is_deleted=False,
            **values,
        )
        row.owner_id = _active_project_person_id(project_id, row.owner or "", db)
    elif proposal.action == "update_workstream":
        row = db.get(models.Task, proposal.target_id)
        if "status" in proposed and TS.normalize(proposed["status"]) == TS.S_COMPLETED:
            _require_workstream_completion(row, db)
        for field, value in proposed.items():
            setattr(row, field, TS.normalize(value) if field == "status" else value)
        row.owner_id = _active_project_person_id(project_id, row.owner or "", db)
        row.edit_count = (row.edit_count or 0) + 1
    elif proposal.action == "create_subtask":
        parent = db.get(models.Task, proposal.parent_workstream_id)
        values = {field: proposed.get(field, "") for field in SUBTASK_FIELDS}
        values["status"] = TS.normalize(values.get("status"))
        if values.get("assignee") and values["status"] == TS.S_NOT_STARTED:
            values["status"] = TS.S_IN_PROGRESS
        row = models.SubTask(
            task_id=proposal.parent_workstream_id,
            is_deleted=False,
            **values,
        )
        row.assignee_id = _active_project_person_id(project_id, row.assignee or "", db)
        db.add(row)
        db.flush()
        _sync_parent_task_status(parent, db, actor)
    elif proposal.action == "update_subtask":
        row = db.get(models.SubTask, proposal.target_id)
        parent = db.get(models.Task, row.task_id)
        before_assignee = (row.assignee or "").strip()
        for field, value in proposed.items():
            setattr(row, field, TS.normalize(value) if field == "status" else value)
        if not before_assignee and (row.assignee or "").strip():
            if TS.normalize(row.status) == TS.S_NOT_STARTED:
                row.status = TS.S_IN_PROGRESS
        row.assignee_id = _active_project_person_id(project_id, row.assignee or "", db)
        _sync_parent_task_status(parent, db, actor)
    elif proposal.action in {"create_execution_schedule", "update_execution_schedule"}:
        proposed = _json_object(proposal.proposed_json)
        if proposal.action == "create_execution_schedule":
            lineage = _project_meeting_lineage(proposal)
            target = lineage.get("target") if isinstance(lineage, dict) and isinstance(lineage.get("target"), dict) else {}
            parent_key_task_id = target.get("key_task_id") if lineage is not None else proposal.parent_workstream_id
            subtask = db.get(models.SubTask, parent_key_task_id)
            if not subtask:
                raise HTTPException(409, "key task no longer exists")
            values = dict(proposed)
            from datetime import date
            for field in ("start_date", "due_date"):
                if values.get(field):
                    values[field] = date.fromisoformat(values[field])
            row = models.ExecutionSchedule(
                subtask_id=subtask.id,
                created_by=actor,
                updated_by=actor,
                is_deleted=False,
                **values,
            )
            db.add(row)
            db.flush()
        else:
            row = db.get(models.ExecutionSchedule, proposal.target_id)
            if not row or row.is_deleted:
                raise HTTPException(409, "execution schedule no longer exists")
            from datetime import date
            for field, value in proposed.items():
                if field in {"start_date", "due_date"} and value:
                    value = date.fromisoformat(value)
                setattr(row, field, value)
            row.updated_by = actor
    else:
        raise HTTPException(409, "proposal action is not executable")

    db.add(row)
    db.flush()
    return row


def _require_workstream_completion(task: models.Task, db: Session) -> None:
    subtasks = (
        db.query(models.SubTask)
        .filter_by(task_id=task.id, is_deleted=False)
        .with_for_update()
        .all()
    )
    if not subtasks:
        raise HTTPException(409, "workstream has no active key tasks")
    if not all(TS.is_completed(row.status) for row in subtasks):
        raise HTTPException(409, "all key tasks must be completed first")


def _sync_parent_task_status(
    task: models.Task,
    db: Session,
    actor: str,
) -> None:
    subtasks = (
        db.query(models.SubTask)
        .filter_by(task_id=task.id, is_deleted=False)
        .all()
    )
    next_status = TS.derive_parent_status(
        task.status,
        [row.status or "" for row in subtasks],
    )
    if TS.normalize(task.status) == next_status:
        return
    before_status = task.status
    task.status = next_status
    task.edit_count = (task.edit_count or 0) + 1
    crud.log(
        db,
        actor,
        "task_sync_status_from_subtasks",
        "task",
        task.id,
        {"status": before_status},
        {"status": next_status},
        project_id=task.project_id,
    )


def _active_project_person_id(project_id: int, name: str, db: Session) -> int | None:
    normalized = (name or "").strip()
    if not normalized:
        return None
    row = (
        db.query(models.Person.id)
        .join(models.ProjectMember, models.ProjectMember.person_id == models.Person.id)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.Person.name == normalized,
            models.Person.is_active.is_(True),
        )
        .first()
    )
    return int(row[0]) if row else None


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)
