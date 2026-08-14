"""Project-context snapshots and evidence-first meeting result validation."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from .project_meeting_agent_contracts import EvidenceSpan, MeetingAgentFinal, MeetingFact, TaskUpdate


_SCHEDULE_FIELDS = {
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
    "collaborator_ids",
    "reminder_policy",
}
_SCHEDULE_FIELD_LIMITS = {
    "plan_month": 7,
    "title": 200,
    "assignee": 50,
    "status": 20,
}
_FACT_COLLECTIONS = (
    "facts",
    "completed_items",
    "next_stage_work",
    "risks",
    "open_questions",
    "decisions",
    "action_items",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _row_values(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _json_value(getattr(row, field, None)) for field in fields}


def _schedule_snapshot(schedule: models.ExecutionSchedule) -> dict[str, Any]:
    return _row_values(
        schedule,
        (
            "id",
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
            "collaborator_ids",
            "reminder_policy",
        ),
    )


def _json_list(value: str | None) -> list[Any]:
    """Return persisted JSON arrays without letting malformed legacy data escape."""
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def build_project_meeting_snapshot(project_id: int, db: Session) -> dict[str, Any]:
    """Freeze the project context used to understand one Word meeting document.

    The snapshot is context only.  It is never used as meeting evidence.  A
    project with no prior ``Meeting`` rows is a valid first-meeting input.
    """
    project = db.get(models.Project, project_id)
    if project is None:
        raise ValueError("project not found")

    members = (
        db.query(models.ProjectMember, models.Person)
        .join(models.Person, models.Person.id == models.ProjectMember.person_id)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.Person.is_active.is_(True),
        )
        .order_by(models.ProjectMember.id.asc())
        .all()
    )
    member_snapshot = [
        {
            "person_id": member.person_id,
            "name": (person.name or "").strip(),
            "role": member.role or "",
        }
        for member, person in members
        if (person.name or "").strip()
    ]

    task_rows = (
        db.query(models.Task)
        .filter(
            models.Task.project_id == project_id,
            models.Task.is_deleted.is_(False),
        )
        .order_by(models.Task.id.asc())
        .all()
    )
    workstreams: list[dict[str, Any]] = []
    for task in task_rows:
        subtask_rows = (
            db.query(models.SubTask)
            .filter(
                models.SubTask.task_id == task.id,
                models.SubTask.is_deleted.is_(False),
            )
            .order_by(models.SubTask.id.asc())
            .all()
        )
        key_tasks: list[dict[str, Any]] = []
        for subtask in subtask_rows:
            schedules = (
                db.query(models.ExecutionSchedule)
                .filter(
                    models.ExecutionSchedule.subtask_id == subtask.id,
                    models.ExecutionSchedule.is_deleted.is_(False),
                )
                .order_by(models.ExecutionSchedule.id.asc())
                .all()
            )
            key_tasks.append(
                {
                    "id": subtask.id,
                    "title": subtask.title or "",
                    "assignee": subtask.assignee or "",
                    "assignee_id": subtask.assignee_id,
                    "plan_time": subtask.plan_time or "",
                    "status": subtask.status or "",
                    "completion_criteria": subtask.completion_criteria or "",
                    "notes": subtask.notes or "",
                    "execution_schedules": [_schedule_snapshot(item) for item in schedules],
                }
            )
        workstreams.append(
            {
                "id": task.id,
                "key_task": task.key_task or "",
                "owner": task.owner or "",
                "owner_id": task.owner_id,
                "coordinator": task.coordinator or "",
                "collaborators": task.collaborators or "",
                "plan_time": task.plan_time or "",
                "status": task.status or "",
                "key_achievement": task.key_achievement or "",
                "completion_standard": task.completion_standard or "",
                "problem_note": task.problem_note or "",
                "key_tasks": key_tasks,
            }
        )

    valid_history = db.query(models.Meeting).filter(
        models.Meeting.project_id == project_id,
        or_(
            models.Meeting.publish_status == "published",
            models.Meeting.review_status == "approved",
        ),
    )
    previous_meeting_ids = [
        meeting_id
        for (meeting_id,) in valid_history.with_entities(models.Meeting.id).order_by(models.Meeting.id.asc()).all()
    ]
    recent_progress_rows = (
        db.query(models.ExecutionSchedule, models.SubTask)
        .join(models.SubTask, models.SubTask.id == models.ExecutionSchedule.subtask_id)
        .join(models.Task, models.Task.id == models.SubTask.task_id)
        .filter(
            models.Task.project_id == project_id,
            models.Task.is_deleted.is_(False),
            models.SubTask.is_deleted.is_(False),
            models.ExecutionSchedule.is_deleted.is_(False),
        )
        .order_by(models.ExecutionSchedule.updated_at.desc(), models.ExecutionSchedule.id.desc())
        .all()
    )
    recent_progress = [
        {
            "key_task_id": key_task.id,
            "execution_schedule_id": schedule.id,
            "content": schedule.progress_note or "",
            "actual_output": schedule.actual_output or "",
            "status": schedule.status or "",
            "updated_at": _json_value(schedule.updated_at),
        }
        for schedule, key_task in recent_progress_rows
    ]
    previous_meeting_rows = (
        valid_history
        .order_by(models.Meeting.meeting_date.desc(), models.Meeting.id.desc())
        .limit(5)
        .all()
    )
    previous_meetings = [
        {
            "meeting_id": meeting.id,
            "meeting_date": meeting.meeting_date or "",
            "title": meeting.title or "",
            "summary": meeting.summary or "",
            "decisions": _json_list(meeting.decision_items_json),
            "actions": _json_list(meeting.task_list_json),
        }
        for meeting in previous_meeting_rows
    ]
    return {
        "project_id": project_id,
        "project": _json_value(
            {
                "id": project.id,
                "name": project.name or "",
                "code": project.code or "",
                "description": project.description or "",
                "objectives": project.objectives or "",
                "status": project.status or "",
                "start_date": project.start_date or "",
                "end_date": project.end_date or "",
                "coordinator": project.coordinator or "",
                "owners": project.owners or "",
            }
        ),
        "members": member_snapshot,
        "workstreams": workstreams,
        "history": {
            "is_first_meeting": not previous_meeting_ids,
            "previous_meeting_ids": previous_meeting_ids,
        },
        "recent_progress": recent_progress,
        "previous_meetings": previous_meetings,
    }


def _document_evidence(evidence: Any, document_text: str | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(evidence, list) or not evidence:
        return [], ["evidence must contain at least one continuous excerpt"]
    if not isinstance(document_text, str) or not document_text:
        return [], ["document_text is required to validate evidence"]
    normalized: list[str] = []
    for item in evidence:
        if not isinstance(item, str) or not item.strip():
            errors.append("evidence excerpts must be non-empty strings")
            continue
        excerpt = item.strip()
        if excerpt not in document_text:
            errors.append("evidence must be an exact continuous substring of document_text")
        else:
            normalized.append(excerpt)
    return normalized, errors


def _schedule_index(
    snapshot: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[int, int | None], dict[int, tuple[int, int | None]], set[int]]:
    schedules: dict[int, dict[str, Any]] = {}
    key_task_parents: dict[int, int | None] = {}
    schedule_parents: dict[int, tuple[int, int | None]] = {}
    member_ids = {
        int(item["person_id"])
        for item in snapshot.get("members", [])
        if isinstance(item, dict) and str(item.get("person_id", "")).isdigit()
    }
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict):
            continue
        workstream_id = workstream.get("id") if isinstance(workstream.get("id"), int) else None
        for key_task in workstream.get("key_tasks", []):
            if not isinstance(key_task, dict) or not isinstance(key_task.get("id"), int):
                continue
            key_task_id = key_task["id"]
            key_task_parents[key_task_id] = workstream_id
            for schedule in key_task.get("execution_schedules", []):
                if isinstance(schedule, dict) and isinstance(schedule.get("id"), int):
                    schedules[schedule["id"]] = schedule
                    schedule_parents[schedule["id"]] = (key_task_id, workstream_id)
    return schedules, key_task_parents, schedule_parents, member_ids


def validate_execution_schedule_proposal(
    raw: Any,
    snapshot: dict[str, Any],
    document_text: str | None,
) -> dict[str, Any]:
    """Validate one schedule change using the Word text as the only evidence."""
    raw = raw if isinstance(raw, dict) else {}
    errors: list[str] = []
    action = str(raw.get("action") or "").strip()
    if action not in {"update_execution_schedule", "create_execution_schedule"}:
        errors.append("action must be update_execution_schedule or create_execution_schedule")

    target_raw = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    target: dict[str, Any] = {"project_id": snapshot.get("project_id")}
    if target_raw.get("project_id") is not None and target_raw.get("project_id") != snapshot.get("project_id"):
        errors.append("target project_id does not match snapshot")

    schedules, key_task_parents, schedule_parents, member_ids = _schedule_index(snapshot)
    schedule_id = target_raw.get("execution_schedule_id")
    key_task_id = target_raw.get("key_task_id", target_raw.get("subtask_id"))
    schedule = None
    if action == "update_execution_schedule":
        if not isinstance(schedule_id, int) or schedule_id not in schedules:
            errors.append("target execution_schedule_id is not present in snapshot")
        else:
            schedule = schedules[schedule_id]
            actual_key_task_id, actual_workstream_id = schedule_parents[schedule_id]
            target["execution_schedule_id"] = schedule_id
            target["key_task_id"] = actual_key_task_id
            target["workstream_id"] = actual_workstream_id
            for parent_field in ("key_task_id", "subtask_id"):
                if parent_field in target_raw and target_raw[parent_field] != actual_key_task_id:
                    errors.append(f"target {parent_field} does not match execution schedule parent key_task_id")
            if "workstream_id" in target_raw and target_raw["workstream_id"] != actual_workstream_id:
                errors.append("target workstream_id does not match execution schedule parent workstream_id")
    elif action == "create_execution_schedule":
        if (
            "key_task_id" in target_raw
            and "subtask_id" in target_raw
            and target_raw["key_task_id"] != target_raw["subtask_id"]
        ):
            errors.append("target key_task_id and subtask_id must match")
        if not isinstance(key_task_id, int) or key_task_id not in key_task_parents:
            errors.append("create_execution_schedule requires an existing key_task_id")
        else:
            target["key_task_id"] = key_task_id
            actual_workstream_id = key_task_parents[key_task_id]
            target["workstream_id"] = actual_workstream_id
            if "workstream_id" in target_raw and target_raw["workstream_id"] != actual_workstream_id:
                errors.append("target workstream_id does not match key_task parent workstream_id")

    proposed_raw = raw.get("proposed") if isinstance(raw.get("proposed"), dict) else {}
    if not isinstance(raw.get("proposed"), dict):
        errors.append("proposed must be an object")
    proposed: dict[str, Any] = {}
    for field, value in proposed_raw.items():
        if field not in _SCHEDULE_FIELDS:
            errors.append(f"proposed contains unsupported field: {field}")
            continue
        if field in _SCHEDULE_FIELD_LIMITS and isinstance(value, str) and len(value) > _SCHEDULE_FIELD_LIMITS[field]:
            errors.append(f"proposed field {field} exceeds its length limit")
            continue
        if field in {"title", "assignee", "status"} and not isinstance(value, str):
            errors.append(f"proposed field {field} must be a string")
            continue
        if field == "plan_type" and value not in {"week", "month"}:
            errors.append("plan_type must be week or month")
            continue
        if field in {"start_date", "due_date"}:
            try:
                value = date.fromisoformat(str(value)).isoformat()
            except ValueError:
                errors.append(f"proposed field {field} must be an ISO date")
                continue
        if field == "assignee_id" and value is not None and value not in member_ids:
            errors.append("assignee_id must belong to an active project member")
            continue
        proposed[field] = _json_value(value)

    start_value = proposed.get("start_date", (schedule or {}).get("start_date"))
    due_value = proposed.get("due_date", (schedule or {}).get("due_date"))
    if start_value and due_value and str(due_value) < str(start_value):
        errors.append("due_date cannot be earlier than start_date")

    evidence, evidence_errors = _document_evidence(raw.get("evidence"), document_text)
    errors.extend(evidence_errors)
    reason = raw.get("reason") if isinstance(raw.get("reason"), str) else ""
    reason = reason.strip()
    if not reason:
        errors.append("reason is required")
    confidence = raw.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("confidence must be between 0 and 1")

    before = dict(schedule or {})
    return {
        "action": action,
        "target": target,
        "before": before,
        "proposed": proposed,
        "evidence": evidence,
        "reason": reason,
        "confidence": confidence if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else 0,
        "validation": {"state": "ready" if not errors else "blocked", "errors": errors},
    }


def _normalize_fact(item: Any, document_text: str | None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "content": "",
            "evidence": [],
            "validation": {"state": "blocked", "errors": ["fact must be an object"]},
        }
    evidence, errors = _document_evidence(item.get("evidence"), document_text)
    normalized = {key: _json_value(value) for key, value in item.items() if key != "validation"}
    normalized["evidence"] = evidence
    normalized["validation"] = {"state": "ready" if not errors else "blocked", "errors": errors}
    return normalized


def normalize_project_meeting_result(
    raw_result: Any,
    document_text: str | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Normalize AI output and block every fact/change lacking Word evidence."""
    raw = raw_result if isinstance(raw_result, dict) else {}
    normalized: dict[str, Any] = {
        "meeting_draft": raw.get("meeting_draft") if isinstance(raw.get("meeting_draft"), dict) else {},
        "facts": [],
        "execution_schedule_changes": [],
        "risks": [],
        "open_questions": [],
        "warnings": [],
    }
    if not isinstance(raw_result, dict):
        normalized["warnings"].append("AI result must be an object")

    for collection in _FACT_COLLECTIONS:
        if collection in raw:
            normalized[collection] = [_normalize_fact(item, document_text) for item in raw.get(collection, [])]
    raw_changes = raw.get("execution_schedule_changes", [])
    if not isinstance(raw_changes, list):
        normalized["warnings"].append("execution_schedule_changes must be a list")
    else:
        normalized["execution_schedule_changes"] = [
            validate_execution_schedule_proposal(item, snapshot, document_text) for item in raw_changes
        ]
    return normalized


def _normalize_agent_evidence(
    evidence: list[EvidenceSpan], document_text: str | None
) -> dict[str, Any]:
    """Verify the agent's quoted character ranges against the frozen Word text."""
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(document_text, str) or not document_text:
        return {
            "evidence": [],
            "validation": {"state": "blocked", "errors": ["document_text is required to validate evidence"]},
        }
    if not evidence:
        return {
            "evidence": [],
            "validation": {"state": "blocked", "errors": ["evidence must contain at least one exact Word span"]},
        }

    for item in evidence:
        if not isinstance(item, EvidenceSpan):
            errors.append("evidence must contain EvidenceSpan objects")
            continue
        payload = item.model_dump(mode="json")
        start = item.char_start
        end = item.char_end
        exact_at_offsets = 0 <= start < end <= len(document_text) and document_text[start:end] == item.quote
        if not exact_at_offsets:
            first_match = document_text.find(item.quote)
            if first_match >= 0 and document_text.find(item.quote, first_match + 1) < 0:
                payload["char_start"] = first_match
                payload["char_end"] = first_match + len(item.quote)
                normalized.append(payload)
                continue
            if start < 0 or end <= start or end > len(document_text):
                errors.append("evidence character range is outside document_text")
            else:
                errors.append("evidence quote does not exactly match document_text character range")
            continue
        normalized.append(payload)

    return {
        "evidence": normalized,
        "validation": {"state": "ready" if not errors else "blocked", "errors": errors},
    }


def _normalize_agent_fact(item: MeetingFact, document_text: str | None) -> dict[str, Any]:
    evidence_result = _normalize_agent_evidence(item.evidence, document_text)
    errors = list(evidence_result["validation"]["errors"])
    if item.needs_confirmation:
        errors.append("fact needs_confirmation requires owner review")
    return {
        "content": item.content,
        "confidence": item.confidence,
        "needs_confirmation": item.needs_confirmation,
        "evidence": evidence_result["evidence"],
        "validation": {"state": "ready" if not errors else "blocked", "errors": errors},
    }


def _normalize_agent_task_update(
    item: TaskUpdate,
    document_text: str | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    evidence_result = _normalize_agent_evidence(item.evidence, document_text)
    proposal = validate_execution_schedule_proposal(
        {
            "action": item.action,
            "target": item.target.model_dump(mode="json", exclude_none=True),
            "before": item.before,
            "proposed": item.proposed,
            "evidence": [span.quote for span in item.evidence],
            "reason": item.reason,
            "confidence": item.confidence,
        },
        snapshot,
        document_text,
    )
    errors = list(proposal["validation"]["errors"])
    errors.extend(evidence_result["validation"]["errors"])
    if item.needs_confirmation:
        errors.append("task update needs_confirmation requires owner review")
    proposal["evidence"] = evidence_result["evidence"]
    proposal["needs_confirmation"] = item.needs_confirmation
    proposal["validation"] = {"state": "ready" if not errors else "blocked", "errors": errors}
    return proposal


def normalize_project_meeting_agent_result(
    final: MeetingAgentFinal,
    document_text: str | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a typed Agent result without weakening Word-evidence safeguards.

    This intentionally sits beside (rather than replacing) the legacy JSON
    normalizer so existing meeting flows keep their current compatibility.
    """
    if not isinstance(final, MeetingAgentFinal):
        raise TypeError("final must be a MeetingAgentFinal")

    meeting_draft = final.meeting_info.model_dump(mode="json")
    meeting_draft["summary"] = final.summary
    meeting_info_evidence = {
        field_name: _normalize_agent_evidence(spans, document_text)
        for field_name, spans in final.meeting_info_evidence.items()
    }
    summary_evidence = _normalize_agent_evidence(final.summary_evidence, document_text)

    return {
        "meeting_draft": meeting_draft,
        "meeting_info_evidence": meeting_info_evidence,
        "summary_evidence": summary_evidence,
        "agenda_items": [_normalize_agent_fact(item, document_text) for item in final.agenda_items],
        "decisions": [_normalize_agent_fact(item, document_text) for item in final.decisions],
        "completed_items": [_normalize_agent_fact(item, document_text) for item in final.completed_items],
        "next_stage_work": [_normalize_agent_fact(item, document_text) for item in final.next_steps],
        "risks": [_normalize_agent_fact(item, document_text) for item in final.risks],
        "open_questions": [_normalize_agent_fact(item, document_text) for item in final.open_questions],
        "execution_schedule_changes": [
            _normalize_agent_task_update(item, document_text, snapshot) for item in final.task_updates
        ],
    }
