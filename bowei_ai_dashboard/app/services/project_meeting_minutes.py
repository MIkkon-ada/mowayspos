"""Project-context snapshots and evidence-first meeting result validation."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..domain import submission_status as SS
from ..domain import source_type as ST
from ..time_utils import utc_now
from .project_meeting_agent_contracts import EvidenceSpan, MeetingAgentFinal, MeetingFact, TaskUpdate
from .meeting_change_set import EXECUTION_SCHEDULE_FIELDS


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
_WRITABLE_EXECUTION_SCHEDULE_FIELDS = frozenset(EXECUTION_SCHEDULE_FIELDS)
_FACT_COLLECTIONS = (
    "facts",
    "completed_items",
    "next_stage_work",
    "risks",
    "open_questions",
    "decisions",
    "action_items",
)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_WORK_REPORT_SOURCE_TYPE_ALIASES = frozenset(
    alias
    for source_type in (ST.MANUAL, ST.VOICE, ST.DOCUMENT)
    for alias in ST.aliases_for(source_type)
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


def _json_object(value: str | None) -> dict[str, Any]:
    """Return persisted JSON objects without exposing malformed legacy data."""
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _meeting_date(meeting: models.Meeting | None) -> date | None:
    return _parse_date(meeting.meeting_date) if meeting is not None else None


def _meeting_window(project: models.Project, published: list[models.Meeting]) -> dict[str, Any]:
    dated_published = [meeting for meeting in published if _meeting_date(meeting) is not None]
    last = max(
        dated_published,
        key=lambda meeting: (_meeting_date(meeting), meeting.id),
        default=None,
    )
    boundary = _meeting_date(last) if last is not None else _parse_date(project.start_date)
    if boundary is None:
        return {
            "start_utc": None,
            "end_utc": None,
            "public": None,
            "diagnostic": "missing_execution_window_start",
        }

    start_date = boundary + timedelta(days=1) if last is not None else boundary
    local_start = datetime.combine(start_date, time.min, tzinfo=_SHANGHAI)
    end_utc = utc_now()
    return {
        "start_utc": local_start.astimezone(timezone.utc).replace(tzinfo=None),
        "end_utc": end_utc,
        "public": {
            "start": local_start.isoformat(),
            "end": end_utc.replace(tzinfo=timezone.utc).astimezone(_SHANGHAI).isoformat(),
            "basis": "last_published_meeting_date" if last is not None else "project_start_date",
            "last_published_meeting_id": last.id if last is not None else None,
        },
        "diagnostic": None,
    }


def _positive_integral_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _submission_task_reports(submission: models.UpdateSubmission) -> list[Any]:
    human = _json_object(submission.human_result_json)
    cards = human.get("task_reports")
    if isinstance(cards, list):
        return cards
    ai = _json_object(submission.ai_result_json)
    cards = ai.get("task_reports")
    return cards if isinstance(cards, list) else []


def _confirmed_report_cards(
    db: Session,
    *,
    project_id: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
    key_task_parent_ids: dict[int, int],
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    rows = (
        db.query(models.UpdateSubmission)
        .filter(
            models.UpdateSubmission.project_id == project_id,
            models.UpdateSubmission.source_type.in_(_WORK_REPORT_SOURCE_TYPE_ALIASES),
            models.UpdateSubmission.confirm_status.in_(SS.CONFIRMED_AND_STORED),
            models.UpdateSubmission.confirmed_at >= window_start_utc,
            models.UpdateSubmission.confirmed_at <= window_end_utc,
        )
        .order_by(models.UpdateSubmission.confirmed_at.asc(), models.UpdateSubmission.id.asc())
        .all()
    )
    cards_by_subtask: dict[int, list[dict[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    for submission in rows:
        for card_index, card in enumerate(_submission_task_reports(submission)):
            parent_task_id = _positive_integral_id(card.get("parent_task_id")) if isinstance(card, dict) else None
            key_task_id = _positive_integral_id(card.get("matched_subtask_id")) if isinstance(card, dict) else None
            if (
                not isinstance(card, dict)
                or card.get("match_status") != "matched"
                or key_task_id is None
                or key_task_parent_ids.get(key_task_id) != parent_task_id
            ):
                diagnostics.append(
                    {
                        "code": "invalid_confirmed_report_card",
                        "source_submission_id": submission.id,
                        "card_index": card_index,
                        "reason": "missing or invalid key-task assignment",
                    }
                )
                continue
            projected = {
                "record_type": "confirmed_report",
                "source_type": "confirmed_report",
                "ingestion_source_type": submission.source_type or "",
                "source_submission_id": submission.id,
                "card_index": card_index,
                "key_task_id": key_task_id,
                "submitter": submission.submitter or "",
                "submitter_id": submission.submitter_id,
                "submitted_at": _json_value(submission.created_at),
                "confirmed_at": _json_value(submission.confirmed_at),
                "confirmation_status": SS.normalize(submission.confirm_status),
                "content": str(card.get("content") or card.get("summary") or ""),
                "actual_output": str(card.get("actual_output") or ""),
                "next_step": str(card.get("next_step") or ""),
            }
            cards_by_subtask.setdefault(key_task_id, []).append(projected)
    return cards_by_subtask, diagnostics


def _confirmed_execution_events(
    db: Session,
    *,
    project_id: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> dict[int, list[dict[str, Any]]]:
    rows = (
        db.query(models.KeyTaskExecutionEvent)
        .join(models.SubTask, models.SubTask.id == models.KeyTaskExecutionEvent.key_task_id)
        .join(models.Task, models.Task.id == models.SubTask.task_id)
        .filter(
            models.KeyTaskExecutionEvent.project_id == project_id,
            models.Task.project_id == project_id,
            models.Task.is_deleted.is_(False),
            models.SubTask.is_deleted.is_(False),
            models.KeyTaskExecutionEvent.authority == "confirmed",
            models.KeyTaskExecutionEvent.occurred_at >= window_start_utc,
            models.KeyTaskExecutionEvent.occurred_at <= window_end_utc,
        )
        .order_by(models.KeyTaskExecutionEvent.occurred_at.asc(), models.KeyTaskExecutionEvent.id.asc())
        .all()
    )
    events_by_subtask: dict[int, list[dict[str, Any]]] = {}
    for event in rows:
        events_by_subtask.setdefault(event.key_task_id, []).append(
            {
                "record_type": "confirmed_event",
                "source_type": event.source_type,
                "source_id": event.source_id,
                "event_id": event.id,
                "key_task_id": event.key_task_id,
                "execution_schedule_id": event.execution_plan_id,
                "event_type": event.event_type,
                "actor": {
                    "person_id": event.actor_person_id,
                    "name": event.actor_name_snapshot or "",
                },
                "occurred_at": _json_value(event.occurred_at),
                "confirmed_at": _json_value(event.confirmed_at),
                "effective_at": _json_value(event.effective_at),
                "status_before": event.status_before,
                "status_after": event.status_after,
                "progress_summary": event.progress_summary or "",
                "next_step": event.next_step or "",
                "affects_current_progress": bool(event.affects_current_progress),
                "display_payload": _json_object(event.display_payload_json),
            }
        )
    return events_by_subtask


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
    key_task_parent_ids: dict[int, int] = {}
    key_task_snapshots: list[tuple[models.SubTask, list[dict[str, Any]], dict[str, Any]]] = []
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
            schedule_snapshots = [_schedule_snapshot(item) for item in schedules]
            key_task_snapshot = {
                "id": subtask.id,
                "title": subtask.title or "",
                "assignee": subtask.assignee or "",
                "assignee_id": subtask.assignee_id,
                "plan_time": subtask.plan_time or "",
                "status": subtask.status or "",
                "completion_criteria": subtask.completion_criteria or "",
                "notes": subtask.notes or "",
                "execution_schedules": schedule_snapshots,
            }
            key_tasks.append(key_task_snapshot)
            key_task_parent_ids[subtask.id] = task.id
            key_task_snapshots.append((subtask, schedule_snapshots, key_task_snapshot))
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

    published_rows = (
        db.query(models.Meeting)
        .filter(
            models.Meeting.project_id == project_id,
            models.Meeting.publish_status == "published",
        )
        .all()
    )
    window = _meeting_window(project, published_rows)
    diagnostics: list[dict[str, Any]] = []
    if window["start_utc"] is None:
        diagnostics.append({"code": window["diagnostic"]})
        report_cards_by_subtask: dict[int, list[dict[str, Any]]] = {}
        events_by_subtask: dict[int, list[dict[str, Any]]] = {}
    else:
        report_cards_by_subtask, diagnostics = _confirmed_report_cards(
            db,
            project_id=project_id,
            window_start_utc=window["start_utc"],
            window_end_utc=window["end_utc"],
            key_task_parent_ids=key_task_parent_ids,
        )
        events_by_subtask = _confirmed_execution_events(
            db,
            project_id=project_id,
            window_start_utc=window["start_utc"],
            window_end_utc=window["end_utc"],
        )
    for subtask, schedule_snapshots, key_task_snapshot in key_task_snapshots:
        key_task_snapshot["execution_context"] = {
            "current_task_baseline": {
                "id": subtask.id,
                "title": subtask.title or "",
                "assignee": subtask.assignee or "",
                "assignee_id": subtask.assignee_id,
                "status": subtask.status or "",
                "plan_time": subtask.plan_time or "",
                "completion_criteria": subtask.completion_criteria or "",
                "notes": subtask.notes or "",
            },
            "current_execution_schedules": schedule_snapshots,
            "confirmed_reports": report_cards_by_subtask.get(subtask.id, []),
            "confirmed_events": events_by_subtask.get(subtask.id, []),
        }

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
        "execution_window": window["public"],
        "diagnostics": diagnostics,
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
        "owner": item.owner,
        "tracker": item.tracker,
        "due_date": item.due_date,
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
    non_evidence_errors = [error for error in errors if "evidence" not in error]
    if item.needs_confirmation:
        errors.append("task update needs_confirmation requires owner review")
    proposal["evidence"] = evidence_result["evidence"]
    proposal["needs_confirmation"] = item.needs_confirmation
    proposal["validation"] = {
        "state": (
            "needs_confirmation"
            if item.needs_confirmation and not non_evidence_errors
            else "ready" if not errors else "blocked"
        ),
        "errors": errors,
    }
    return proposal


_STATUS_NORMALIZATIONS = {"已完成": "completed", "完成": "completed", "已经完成": "completed", "进行中": "in_progress", "正在推进": "in_progress"}
_ALLOWED_STATUS_VALUES = {"completed", "in_progress", "blocked", "not_started"}
_DATE_FIELD_NAMES = {"start_date", "due_date"}


def _analysis_validation(errors: list[str]) -> dict[str, Any]:
    return {"state": "ready" if not errors else "blocked", "errors": errors}


def _analysis_snapshot_objects(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    objects: dict[str, dict[str, Any]] = {}
    workstreams: dict[int, dict[str, Any]] = {}
    key_tasks: dict[int, dict[str, Any]] = {}
    schedules: dict[int, dict[str, Any]] = {}
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict) or not isinstance(workstream.get("id"), int):
            continue
        workstreams[workstream["id"]] = workstream
        objects[f"workstream:{workstream['id']}"] = workstream
        for key_task in workstream.get("key_tasks", []):
            if not isinstance(key_task, dict) or not isinstance(key_task.get("id"), int):
                continue
            key_tasks[key_task["id"]] = key_task
            objects[f"key_task:{key_task['id']}"] = key_task
            for schedule in key_task.get("execution_schedules", []):
                if isinstance(schedule, dict) and isinstance(schedule.get("id"), int):
                    schedules[schedule["id"]] = schedule
                    objects[f"execution_schedule:{schedule['id']}"] = schedule
    return objects, workstreams, key_tasks, schedules


def _normalize_analysis_field(field_name: str, sourced_value: Any, document_text: str | None) -> dict[str, Any]:
    evidence_result = _normalize_agent_evidence(sourced_value.evidence, document_text)
    errors = list(evidence_result["validation"]["errors"])
    if not any(sourced_value.raw_text in span["quote"] for span in evidence_result["evidence"]):
        errors.append("raw_text must be exactly covered by field-level Word evidence")
    raw_text = sourced_value.raw_text
    value = sourced_value.value
    if field_name == "status":
        expected = _STATUS_NORMALIZATIONS.get(raw_text)
        if expected is None and raw_text in _ALLOWED_STATUS_VALUES:
            expected = raw_text
        if expected is None:
            errors.append("status raw_text is not an allowed deterministic status")
        elif value != expected:
            errors.append("status value is not a permitted deterministic normalization of raw_text")
    elif field_name in _DATE_FIELD_NAMES:
        chinese_date = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw_text)
        iso_date = re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_text)
        try:
            expected = date.fromisoformat(raw_text).isoformat() if iso_date else (
                date(int(chinese_date.group(1)), int(chinese_date.group(2)), int(chinese_date.group(3))).isoformat()
                if chinese_date else None
            )
        except ValueError:
            expected = None
        if expected is None:
            errors.append("date raw_text must use YYYY-MM-DD or YYYY年M月D日")
        elif value != expected:
            errors.append("date value is not a permitted deterministic normalization of raw_text")
    elif value != raw_text:
        errors.append("field value must conservatively equal raw_text")
    return {"value": _json_value(value), "raw_text": raw_text, "evidence": evidence_result["evidence"], "provenance": sourced_value.provenance.model_dump(mode="json"), "validation": _analysis_validation(errors)}


def _normalize_analysis_fact(item: Any, document_text: str | None) -> dict[str, Any]:
    evidence_result = _normalize_agent_evidence(item.meeting_evidence, document_text)
    fields = {name: _normalize_analysis_field(name, value, document_text) for name, value in item.fields.items()}
    errors = list(evidence_result["validation"]["errors"])
    if any(field["validation"]["state"] != "ready" for field in fields.values()):
        errors.append("one or more fact fields failed field-level evidence validation")
    return {"fact_id": item.fact_id, "fact_type": item.fact_type, "content": item.content, "fields": fields, "meeting_evidence": evidence_result["evidence"], "confidence": item.confidence, "needs_confirmation": item.needs_confirmation, "validation": _analysis_validation(errors)}


def _normalize_analysis_match(item: Any, facts: dict[str, dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    objects, workstreams, key_tasks, schedules = _analysis_snapshot_objects(snapshot)
    _, key_task_parents, schedule_parents, _ = _schedule_index(snapshot)
    errors: list[str] = []
    if item.fact_id not in facts or facts[item.fact_id]["validation"]["state"] != "ready":
        errors.append("match fact_id is not a ready meeting fact")
    target = {"target_type": item.target_type, "target_id": item.target_id, "workstream_id": item.workstream_id, "key_task_id": item.key_task_id}
    if item.target_type == "execution_schedule":
        schedule = schedules.get(item.target_id)
        if schedule is None or schedule_parents.get(item.target_id) != (item.key_task_id, item.workstream_id):
            errors.append("match target execution schedule is not in frozen snapshot hierarchy")
    elif item.target_type == "key_task":
        if item.target_id not in key_tasks or item.key_task_id != item.target_id or key_task_parents.get(item.target_id) != item.workstream_id:
            errors.append("match target key task is not in frozen snapshot hierarchy")
    elif item.target_type == "workstream" and (item.target_id not in workstreams or item.workstream_id != item.target_id):
        errors.append("match target workstream is not in frozen snapshot hierarchy")
    evidence: list[dict[str, Any]] = []
    for proof in item.project_evidence:
        source = objects.get(proof.source_object)
        if source is None or proof.field not in source or _json_value(source[proof.field]) != _json_value(proof.value):
            errors.append("project evidence must exactly reference a frozen snapshot field")
        evidence.append(proof.model_dump(mode="json"))
    return {"match_id": item.match_id, "fact_id": item.fact_id, "target": target, "confidence": item.confidence, "reasons": list(item.reasons), "project_evidence": evidence, "validation": _analysis_validation(errors)}


def _normalize_analysis_delta(item: Any, facts: dict[str, dict[str, Any]], matches: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if item.source_fact_id not in facts or facts[item.source_fact_id]["validation"]["state"] != "ready":
        errors.append("delta source_fact_id is not a ready meeting fact")
    if item.source_match_id and (item.source_match_id not in matches or matches[item.source_match_id]["validation"]["state"] != "ready"):
        errors.append("delta source_match_id is not a ready project match")
    if item.delta_type not in {"UNMATCHED", "AMBIGUOUS"} and not item.source_match_id:
        errors.append("matched delta requires source_match_id")
    return {"delta_id": item.delta_id, "source_fact_id": item.source_fact_id, "source_match_id": item.source_match_id, "delta_type": item.delta_type, "reasoning": item.reasoning, "validation": _analysis_validation(errors)}


def _change_target_matches_project_match(item: Any, target: dict[str, Any], match: dict[str, Any]) -> bool:
    match_target = match["target"]
    if (
        target.get("workstream_id") != match_target["workstream_id"]
        or target.get("key_task_id") != match_target["key_task_id"]
    ):
        return False
    if match_target["target_type"] == "execution_schedule":
        return (
            item.action == "update_execution_schedule"
            and target.get("execution_schedule_id") == match_target["target_id"]
        )
    return True


def _normalize_analysis_change(item: Any, facts: dict[str, dict[str, Any]], matches: dict[str, dict[str, Any]], deltas: dict[str, dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    objects, _, key_tasks, schedules = _analysis_snapshot_objects(snapshot)
    _, key_task_parents, schedule_parents, _ = _schedule_index(snapshot)
    errors: list[str] = []
    fact = facts.get(item.source_fact_id)
    match = matches.get(item.source_match_id)
    delta = deltas.get(item.source_delta_id)
    if not fact or fact["validation"]["state"] != "ready" or not match or match["validation"]["state"] != "ready" or not delta or delta["validation"]["state"] != "ready":
        errors.append("proposed change requires ready fact, match, and delta")
    if delta and delta["delta_type"] in {"UNMATCHED", "AMBIGUOUS"}:
        errors.append("unmatched or ambiguous delta cannot create a writable proposal")
    target = item.target.model_dump(mode="json", exclude_none=True)
    if target.get("project_id") != snapshot.get("project_id"):
        errors.append("proposal target project_id does not match frozen snapshot")
    if match and not _change_target_matches_project_match(item, target, match):
        errors.append("proposal target does not match project match target")
    if item.action == "update_execution_schedule":
        schedule = schedules.get(target.get("execution_schedule_id"))
        if schedule is None or schedule_parents.get(target.get("execution_schedule_id")) != (target.get("key_task_id"), target.get("workstream_id")):
            errors.append("update target execution_schedule_id is not in frozen snapshot")
    elif target.get("key_task_id") not in key_tasks or key_task_parents.get(target.get("key_task_id")) != target.get("workstream_id"):
        errors.append("create target key_task_id is not in frozen snapshot")
    unsupported_fields = sorted(set(item.proposed) - _WRITABLE_EXECUTION_SCHEDULE_FIELDS)
    if unsupported_fields:
        errors.append("proposed contains unsupported execution schedule fields: " + ", ".join(unsupported_fields))
    field_sources = {name: source.model_dump(mode="json") for name, source in item.field_sources.items()}
    for field_name, source in item.field_sources.items():
        if source.source_type == "meeting_fact":
            source_fact = facts.get(source.source_fact_id or "")
            field = (source_fact or {}).get("fields", {}).get(field_name)
            if not source_fact or not field or field["validation"]["state"] != "ready" or item.proposed.get(field_name) != field.get("value"):
                errors.append(f"meeting_fact field source is not supported for {field_name}")
        elif source.source_type == "project_baseline":
            source_object = objects.get(source.source_object or "")
            if not source_object or source.source_field not in source_object or _json_value(source_object[source.source_field]) != _json_value(item.proposed.get(field_name)):
                errors.append(f"project_baseline source is not an exact snapshot value for {field_name}")
        else:
            errors.append("human_edit is not valid in agent proposed changes")
    return {"change_id": item.change_id, "source_fact_id": item.source_fact_id, "source_match_id": item.source_match_id, "source_delta_id": item.source_delta_id, "action": item.action, "target": target, "before": _json_value(item.before), "proposed": _json_value(item.proposed), "field_sources": field_sources, "requires_confirmation": item.requires_confirmation, "validation": _analysis_validation(errors)}


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
    meeting_facts = [_normalize_analysis_fact(item, document_text) for item in final.meeting_facts]
    fact_index = {item["fact_id"]: item for item in meeting_facts}
    project_matches = [_normalize_analysis_match(item, fact_index, snapshot) for item in final.project_matches]
    match_index = {item["match_id"]: item for item in project_matches}
    project_deltas = [_normalize_analysis_delta(item, fact_index, match_index) for item in final.project_deltas]
    delta_index = {item["delta_id"]: item for item in project_deltas}
    proposed_changes = [
        _normalize_analysis_change(item, fact_index, match_index, delta_index, snapshot)
        for item in final.proposed_changes
    ]
    legacy_changes = [
        _normalize_agent_task_update(item, document_text, snapshot) for item in final.task_updates
    ]
    for change in proposed_changes:
        if change["validation"]["state"] != "ready":
            continue
        fact = fact_index[change["source_fact_id"]]
        evidence = [
            span
            for field in fact["fields"].values()
            for span in field["evidence"]
        ]
        legacy_changes.append({
            "action": change["action"], "target": change["target"], "before": change["before"],
            "proposed": change["proposed"], "evidence": evidence,
            "reason": delta_index[change["source_delta_id"]]["reasoning"], "confidence": 0,
            "needs_confirmation": True, "validation": change["validation"],
        })

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
        "execution_schedule_changes": legacy_changes,
        "meeting_facts": meeting_facts,
        "project_matches": project_matches,
        "project_deltas": project_deltas,
        "proposed_changes": proposed_changes,
        "unmatched_items": [_normalize_analysis_fact(item, document_text) for item in final.unmatched_items],
        "needs_confirmation": [_normalize_analysis_fact(item, document_text) for item in final.needs_confirmation],
    }
