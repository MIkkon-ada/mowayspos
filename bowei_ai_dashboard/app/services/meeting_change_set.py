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
    "Not started",
    "In progress",
    "Done",
    "Completed",
    "Delayed",
    "Paused",
    "Archived",
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
        if key == "status" and TS.normalize(normalized) not in ALLOWED_STATUS_VALUES:
            errors.append("proposed.status is not an allowed task status")
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
    for proposal in proposals:
        if proposal.execution_status != "pending":
            raise HTTPException(409, "selected proposal is not pending")
        validation = _json_object(proposal.validation_json)
        if validation.get("state") == "blocked":
            raise HTTPException(409, "blocked proposal cannot be executed")
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


def _apply_validated_proposal(
    proposal: models.MeetingChangeProposal,
    project_id: int,
    actor: str,
    db: Session,
) -> models.Task | models.SubTask:
    proposed = _json_object(proposal.proposed_json)
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
