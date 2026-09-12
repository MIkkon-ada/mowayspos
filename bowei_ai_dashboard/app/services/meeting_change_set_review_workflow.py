"""Application commands for reviewing and executing meeting change sets."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain.workflow_permissions import (
    A_MEETING_APPLY_CHANGES,
    A_MEETING_REVIEW_CHANGES,
)
from ..permissions import (
    PROJECT_ROLE_OWNER_KEY,
    get_user_context_from_db,
    require_login,
    require_project_access,
)
from ..services import policy as P
from ..services.meeting_change_set import (
    edit_meeting_change_proposal,
    edit_project_meeting_lineage_proposal,
    execute_meeting_change_set as execute_change_set_domain,
)
from ..services.project_resolution import resolve_project_context


def _json_value(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def meeting_change_proposal_payload(
    row: models.MeetingChangeProposal,
    project_id: int,
) -> dict:
    validation = _json_value(row.validation_json, {"state": "blocked", "errors": []})
    lineage = _json_value(row.lineage_json, {})
    target = {"project_id": project_id}
    if row.target_type == "workstream" and row.target_id is not None:
        target["workstream_id"] = row.target_id
    if row.target_type == "subtask" and row.target_id is not None:
        target["subtask_id"] = row.target_id
    if row.target_type == "execution_schedule" and row.target_id is not None:
        target["execution_schedule_id"] = row.target_id
    if row.parent_workstream_id is not None:
        target["parent_workstream_id"] = row.parent_workstream_id
    return {
        "id": row.id,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "parent_workstream_id": row.parent_workstream_id,
        "target": target,
        "before": _json_value(row.before_json, {}),
        "proposed": _json_value(row.proposed_json, {}),
        "evidence": _json_value(row.evidence_json, []),
        "reason": row.reason,
        "confidence": row.confidence,
        "validation": validation,
        "execution_status": row.execution_status,
        "executed_by_person_id": row.executed_by_person_id,
        "executed_at": row.executed_at,
        "result_target_id": row.result_target_id,
        "lineage": lineage,
        "conflict_reason": validation.get("errors", [])
        if row.execution_status == "conflict"
        else [],
    }


def meeting_change_set_payload(
    row: models.MeetingChangeSet,
    db: Session,
) -> dict:
    proposals = (
        db.query(models.MeetingChangeProposal)
        .filter_by(change_set_id=row.id)
        .order_by(models.MeetingChangeProposal.id.asc())
        .all()
    )
    return {
        "id": row.id,
        "project_id": row.project_id,
        "status": row.status,
        "proposals": [
            meeting_change_proposal_payload(proposal, row.project_id)
            for proposal in proposals
        ],
    }


def _require_workflow_action(
    context: dict,
    project_id: int | None,
    action: str,
    db: Session,
) -> None:
    decision = P.decide_workflow_for_project(context, project_id, action, db)
    if not decision.allowed:
        raise HTTPException(decision.status_code, decision.detail or "permission denied")


def _row_project_id(row: models.Meeting, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        related_special_project=row.related_special_project or "",
    )["project_id"]


def _can_view_meeting_draft(
    row: models.Meeting,
    current_user: str,
    context: dict,
    db: Session,
) -> bool:
    if context.get("is_tech_admin") or context.get("is_ceo"):
        return True
    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    if account and account.person_id and row.creator_person_id == account.person_id:
        return True
    return bool(
        row.project_id
        and db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == row.project_id,
            models.ProjectMember.person_id == (account.person_id if account else None),
            models.ProjectMember.role == PROJECT_ROLE_OWNER_KEY,
        )
        .first()
    )


def _meeting_for_read(
    row_id: int,
    current_user: str,
    db: Session,
) -> models.Meeting:
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")
    project_id = _row_project_id(row, db)
    if row.publish_status != "published" and not _can_view_meeting_draft(
        row,
        current_user,
        context,
        db,
    ):
        raise HTTPException(403, "permission denied")
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return row


def _change_set_for_meeting(
    meeting_id: int,
    db: Session,
) -> models.MeetingChangeSet:
    row = db.query(models.MeetingChangeSet).filter_by(meeting_id=meeting_id).first()
    if not row:
        raise HTTPException(404, "meeting change set not found")
    return row


def _proposal_for_change_set(
    proposal_id: int,
    change_set_id: int,
    db: Session,
) -> models.MeetingChangeProposal:
    row = (
        db.query(models.MeetingChangeProposal)
        .filter_by(id=proposal_id, change_set_id=change_set_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "meeting change proposal not found")
    return row


def get_meeting_change_set(
    *,
    row_id: int,
    current_user: str,
    db: Session,
) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    return meeting_change_set_payload(_change_set_for_meeting(meeting.id, db), db)


def patch_meeting_change_proposal(
    *,
    row_id: int,
    proposal_id: int,
    payload: schemas.MeetingChangeProposalPatch,
    current_user: str,
    db: Session,
) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    change_set = _change_set_for_meeting(meeting.id, db)
    proposal = _proposal_for_change_set(proposal_id, change_set.id, db)
    if _json_value(proposal.lineage_json, {}):
        context = get_user_context_from_db(current_user, db)
        _require_workflow_action(
            context,
            change_set.project_id,
            A_MEETING_REVIEW_CHANGES,
            db,
        )
        edit_project_meeting_lineage_proposal(
            proposal=proposal,
            change_set=change_set,
            meeting=meeting,
            actor=current_user,
            proposed_updates=payload.proposed,
            db=db,
        )
    else:
        edit_meeting_change_proposal(
            proposal=proposal,
            change_set=change_set,
            transcript_text=meeting.transcript_text or "",
            proposed=payload.proposed,
            evidence=payload.evidence,
            reason=payload.reason,
            db=db,
        )
    db.commit()
    db.refresh(proposal)
    return meeting_change_proposal_payload(proposal, change_set.project_id)


def execute_meeting_change_set(
    *,
    row_id: int,
    payload: schemas.MeetingChangeSetExecutePayload,
    current_user: str,
    db: Session,
) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    context = get_user_context_from_db(current_user, db)
    _require_workflow_action(
        context,
        meeting.project_id,
        A_MEETING_APPLY_CHANGES,
        db,
    )
    proposals = execute_change_set_domain(
        meeting=meeting,
        proposal_ids=payload.proposal_ids,
        actor=current_user,
        db=db,
    )
    for proposal in proposals:
        proposed = _json_value(proposal.proposed_json, {})
        evidence = _json_value(proposal.evidence_json, [])
        crud.log(
            db,
            current_user,
            "meeting_change_execute",
            "meeting_change_proposal",
            proposal.id,
            {
                "proposal_id": proposal.id,
                "before": _json_value(proposal.before_json, {}),
                "proposed": proposed,
                "evidence": evidence,
            },
            {
                "proposal_id": proposal.id,
                "proposed": proposed,
                "evidence": evidence,
                "result_target_id": proposal.result_target_id,
                "execution_status": proposal.execution_status,
            },
            project_id=meeting.project_id,
        )
    db.commit()
    return meeting_change_set_payload(_change_set_for_meeting(meeting.id, db), db)
