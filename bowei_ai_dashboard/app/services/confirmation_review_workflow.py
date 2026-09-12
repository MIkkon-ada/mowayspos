"""Shared identity, access, and state helpers for confirmation review workflows."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain import submission_status as SS
from ..domain.workflow_permissions import A_CONFIRMATION_REVIEW
from ..permissions import (
    can_access_confirmation_center,
    can_assign_submission,
    get_user_context_from_db,
    require_project_owner_or_admin,
)
from ..services import policy as P
from ..services import workflow as W
from ..services.project_close import require_project_business_writable
from ..services.project_resolution import resolve_project_context


def load_submission(db: Session, submission_id: int) -> models.UpdateSubmission:
    row = db.get(models.UpdateSubmission, submission_id)
    if not row:
        raise HTTPException(404, "confirmation not found")
    return row


def unique_active_person_id_for_name(db: Session, name: str) -> int | None:
    rows = (
        db.query(models.Person.id)
        .filter(models.Person.name == name, models.Person.is_active.is_(True))
        .limit(2)
        .all()
    )
    return rows[0][0] if len(rows) == 1 else None


def is_submission_submitter(
    row: models.UpdateSubmission,
    context: dict,
    current_user: str,
    db: Session,
) -> bool:
    """Use submitter_id for new rows; only legacy rows may match stored strings."""
    if row.submitter_id is not None:
        person_id = context.get("person_id")
        return person_id is not None and row.submitter_id == person_id

    submitter = (row.submitter or "").strip()
    current_user = (current_user or "").strip()
    if submitter and submitter == current_user:
        return True

    person_id = context.get("person_id")
    context_name = (context.get("name") or "").strip()
    return bool(
        submitter
        and person_id is not None
        and context_name
        and submitter == context_name
        and unique_active_person_id_for_name(db, context_name) == person_id
    )


def submission_recipient_id(
    row: models.UpdateSubmission,
    db: Session,
) -> int | None:
    """Resolve a submitter notification recipient without re-resolving new rows."""
    if row.submitter_id is not None:
        return row.submitter_id
    if not row.submitter:
        return None
    from ..services.notify import person_id_for_account

    return (
        person_id_for_account(row.submitter, db)
        or unique_active_person_id_for_name(db, row.submitter.strip())
    )


def submission_project_context(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> dict:
    payload = json_payload if json_payload is not None else W.submission_result(row)
    return resolve_project_context(
        db,
        project_id=row.project_id,
        json_payload=payload,
        parent_task_id=row.related_task_id,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )


def submission_project_id(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> int | None:
    return submission_project_context(
        db,
        row,
        json_payload=json_payload,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )["project_id"]


def submission_project_name(
    db: Session,
    row: models.UpdateSubmission,
    *,
    json_payload: dict | None = None,
    allow_parent_task_lookup: bool = True,
) -> str:
    context = submission_project_context(
        db,
        row,
        json_payload=json_payload,
        allow_parent_task_lookup=allow_parent_task_lookup,
    )
    if context.get("project_name"):
        return context["project_name"]
    payload = json_payload if json_payload is not None else W.submission_result(row)
    task = payload.get("task") if isinstance(payload, dict) and isinstance(payload.get("task"), dict) else {}
    return (
        task.get("special_project")
        or payload.get("special_project")
        or task.get("project_name")
        or payload.get("project_name")
        or task.get("projectName")
        or payload.get("projectName")
        or ""
    )


def resolve_pending_project_id(
    db: Session,
    project_id: int | None,
    special_project: str | None,
) -> int | None:
    if project_id is not None:
        return project_id
    if not special_project:
        return None
    return resolve_project_context(db, special_project=special_project)["project_id"]


def require_submission_project_access(
    row: models.UpdateSubmission,
    context: dict,
    db: Session | None = None,
) -> int | None:
    project_id = submission_project_id(db, row) if db is not None else P.project_id_of(row)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(422, "submission missing project_id")
    return project_id


def require_submission_writable(
    row: models.UpdateSubmission,
    context: dict,
    db: Session,
) -> int | None:
    """Confirmation writes validate project access before project lifecycle writability."""
    project_id = require_submission_project_access(row, context, db)
    require_project_business_writable(project_id, db)
    return project_id


def require_submission_owner_or_admin(
    row: models.UpdateSubmission,
    context: dict,
    current_user: str,
    db: Session,
) -> int | None:
    project_id = require_submission_project_access(row, context, db)
    if project_id is None:
        return None
    require_project_owner_or_admin(current_user, project_id, db)
    return project_id


def require_confirmation_center(context: dict) -> None:
    if context.get("is_tech_admin"):
        return
    if not can_access_confirmation_center(context):
        raise HTTPException(403, "permission denied")


def can_owner_style_action(
    context: dict,
    row: models.UpdateSubmission,
    db: Session,
    *,
    allow_assign: bool = False,
) -> bool:
    if context.get("is_tech_admin"):
        return True
    if P.decide_workflow_for_project(
        context,
        row.project_id,
        A_CONFIRMATION_REVIEW,
        db,
    ).allowed:
        return True
    if allow_assign and can_assign_submission(context):
        return True
    return False


def require_owner_style_actor(
    context: dict,
    row: models.UpdateSubmission,
    db: Session,
    *,
    allow_assign: bool = False,
) -> None:
    if context.get("is_tech_admin"):
        return
    if can_owner_style_action(context, row, db, allow_assign=allow_assign):
        return
    raise HTTPException(403, "permission denied")


_CARD_WORKFLOW_FIELDS = frozenset(
    {
        "confirmation_status",
        "confirmation_note",
        "confirmation_operator",
        "confirmation_at",
        "coordinator_request_note",
        "coordinator_request_operator",
        "coordinator_requested_at",
        "coordinator_note",
        "coordinator_operator",
        "coordinator_feedback_at",
        "ceo_note",
        "ceo_operator",
        "ceo_decided_at",
    }
)


def _task_reports(data: dict) -> list[dict]:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        raise HTTPException(400, "task_reports must be a list")
    return reports


def _card_confirmation_status(report: dict) -> str:
    return (report.get("confirmation_status") or "").strip()


def _has_pending_ceo_task_cards(data: dict) -> bool:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        return False
    return any(
        isinstance(report, dict) and _card_confirmation_status(report) == "pending_ceo_decision"
        for report in reports
    )


def _has_pending_coordinator_task_cards(data: dict) -> bool:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        return False
    return any(
        isinstance(report, dict) and _card_confirmation_status(report) == "transferred_to_coordinator"
        for report in reports
    )


def require_no_pending_ceo_cards(data: dict) -> None:
    if _has_pending_ceo_task_cards(data):
        raise HTTPException(409, "submission contains task cards waiting for coach decision")


def require_no_pending_coordinator_cards(data: dict) -> None:
    if _has_pending_coordinator_task_cards(data):
        raise HTTPException(409, "submission contains task cards waiting for coordinator feedback")


def merge_card_confirmation_payload(data: dict, human_result: dict | None) -> dict:
    """Merge owner edits while retaining persisted task-card workflow fields."""
    if not human_result:
        return data
    incoming = dict(human_result)
    if "task_reports" in incoming:
        persisted_reports = _task_reports(data)
        incoming_reports = incoming["task_reports"]
        if not isinstance(incoming_reports, list) or len(incoming_reports) != len(persisted_reports):
            raise HTTPException(409, "task card list cannot be changed during confirmation")
        merged_reports: list[dict] = []
        for persisted_report, incoming_report in zip(persisted_reports, incoming_reports):
            if not isinstance(persisted_report, dict) or not isinstance(incoming_report, dict):
                raise HTTPException(400, "task card is not an object")
            merged_report = dict(incoming_report)
            for field in _CARD_WORKFLOW_FIELDS:
                merged_report.pop(field, None)
                if field in persisted_report:
                    merged_report[field] = persisted_report[field]
            merged_reports.append(merged_report)
        incoming["task_reports"] = merged_reports
    merged = dict(data)
    merged.update(incoming)
    return merged


def save_submission_review(
    *,
    submission_id: int,
    payload: schemas.ConfirmationSaveRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    require_owner_style_actor(context, row, db, allow_assign=True)
    before = crud.to_dict(row)
    data = W.submission_result(row)
    require_no_pending_ceo_cards(data)
    require_no_pending_coordinator_cards(data)
    merged_data = merge_card_confirmation_payload(data, payload.human_result)
    row.human_result_json = json.dumps(merged_data, ensure_ascii=False)
    row.confirm_status = SS.S_NEEDS_REVISION
    crud.log(db, current_user or "管理员", "confirmation_update", "confirmation", row.id, before, merged_data)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def return_submission_to_submitter(
    *,
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    require_owner_style_actor(context, row, db)
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)
    before = crud.to_dict(row)
    data = W.submission_result(row)
    require_no_pending_ceo_cards(data)
    require_no_pending_coordinator_cards(data)
    project_id = submission_project_id(db, row)
    row.confirm_status = SS.S_RETURNED
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_return", "confirmation", row.id, before, {"reason": payload.reason})
    if row.submitter_id is not None or row.submitter:
        recipient_id = submission_recipient_id(row, db)
        if recipient_id is not None:
            from ..services.notify import send as notify

            notify(
                db,
                recipient_id=recipient_id,
                recipient=row.submitter,
                ntype="submission_rejected",
                title=f"你的提交被打回：{row.title or '（无标题）'}",
                body=f"打回原因：{payload.reason or '未说明'}，请补充后重新提交",
                link=f"/work/submit?history=1&submissionId={row.id}",
                project_id=project_id,
            )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def resubmit_submission(
    *,
    submission_id: int,
    payload: schemas.ResubmitRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    require_submission_writable(row, context, db)
    operator = payload.operator or current_user
    if not is_submission_submitter(row, context, current_user, db):
        raise HTTPException(403, "只有原提交人可以重新提交")
    W.require_submission_status(row, SS.RETURNED_TO_SUBMITTER)
    before = crud.to_dict(row)
    project_id = submission_project_id(db, row)
    if payload.human_result:
        new_result = dict(payload.human_result)
        if payload.supplement_note:
            new_result["supplement_note"] = payload.supplement_note
        row.human_result_json = json.dumps(new_result, ensure_ascii=False)
    elif payload.supplement_note:
        existing = W.json_or_empty(row.human_result_json or row.ai_result_json)
        existing["supplement_note"] = payload.supplement_note
        row.human_result_json = json.dumps(existing, ensure_ascii=False)
    row.confirm_status = SS.S_PENDING_OWNER
    row.reject_reason = None
    crud.log(db, operator, "confirmation_resubmit", "confirmation", row.id, before, {"note": payload.supplement_note or ""})
    if project_id:
        from ..services.notify import project_strict_owner_ids, send as notify

        submitter_id = context.get("person_id")
        for owner_id in project_strict_owner_ids(project_id, db):
            if owner_id != submitter_id:
                notify(
                    db,
                    recipient_id=owner_id,
                    ntype="submission_resubmitted",
                    title=f"提交人已重新提交：{row.title or '（无标题）'}",
                    body=f"提交人：{operator}，请前往 AI 确认中心处理",
                    link=(f"/work/confirmations?view=all"
                          f"{'&projectId=' + str(project_id) if project_id is not None else ''}"
                          f"&submissionId={row.id}"),
                    project_id=project_id,
                )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def withdraw_submission(
    *,
    submission_id: int,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user, db)
    require_submission_writable(row, context, db)
    is_tech_admin = context.get("is_tech_admin", False)
    if not is_submission_submitter(row, context, current_user, db) and not is_tech_admin:
        raise HTTPException(403, "只有原提交人或管理员可以撤回")
    W.require_submission_status(row, SS.WITHDRAWABLE)
    before = crud.to_dict(row)
    data = W.submission_result(row)
    require_no_pending_ceo_cards(data)
    require_no_pending_coordinator_cards(data)
    row.confirm_status = SS.S_WITHDRAWN
    crud.log(db, current_user, "confirmation_withdraw", "confirmation", row.id, before, {})
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def reject_submission_finally(
    *,
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    require_owner_style_actor(context, row, db)
    before = crud.to_dict(row)
    data = W.submission_result(row)
    require_no_pending_ceo_cards(data)
    require_no_pending_coordinator_cards(data)
    project_id = submission_project_id(db, row)
    row.confirm_status = SS.S_PERMANENTLY_REJECTED
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_mark_not_imported", "confirmation", row.id, before, {"reason": payload.reason})
    if row.submitter_id is not None or row.submitter:
        recipient_id = submission_recipient_id(row, db)
        if recipient_id is not None:
            from ..services.notify import send as notify

            notify(
                db,
                recipient_id=recipient_id,
                recipient=row.submitter,
                ntype="submission_rejected",
                title=f"你的提交被标记为不入库：{row.title or '（无标题）'}",
                body=f"原因：{payload.reason or '未说明'}",
                link=f"/work/submit?history=1&submissionId={row.id}",
                project_id=project_id,
            )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def mark_submission_unrecognized(
    *,
    submission_id: int,
    payload: schemas.RejectRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    if not can_owner_style_action(context, row, db, allow_assign=True):
        raise HTTPException(403, "permission denied")
    before = crud.to_dict(row)
    data = W.submission_result(row)
    require_no_pending_ceo_cards(data)
    require_no_pending_coordinator_cards(data)
    row.confirm_status = SS.S_NEEDS_REVISION
    row.reject_reason = payload.reason
    crud.log(db, payload.operator, "confirmation_mark_unrecognized", "confirmation", row.id, before, {"reason": payload.reason})
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}


def assign_submission_owner(
    *,
    submission_id: int,
    payload: schemas.AssignRequest,
    current_user: str,
    db: Session,
) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    require_owner_style_actor(context, row, db, allow_assign=True)
    before = crud.to_dict(row)
    project_id = submission_project_id(db, row)
    data = W.submission_result(row)
    require_no_pending_coordinator_cards(data)
    data["assigned_to"] = payload.assignee
    if "task" in data:
        data["task"]["owner"] = payload.assignee
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    row.confirm_status = SS.S_PENDING_OWNER
    crud.log(db, payload.operator, "confirmation_assign_owner", "confirmation", row.id, before, data)
    if payload.assignee:
        from ..services.notify import (
            person_id_for_account,
            person_id_for_name,
            person_name_for_account,
            send as notify,
        )

        caller_name = person_name_for_account(current_user or payload.operator, db)
        caller_id = person_id_for_account(current_user or payload.operator, db)
        assignee_id = person_id_for_name(payload.assignee, db)
        if payload.assignee != caller_name and assignee_id != caller_id:
            notify(
                db,
                recipient_id=assignee_id,
                recipient=payload.assignee,
                ntype="submission_assigned",
                title=f"有提交指定由你负责：{row.title or '（无标题）'}",
                body=f"指定人：{caller_name}，请前往 AI 确认中心处理",
                link=f"/project/{project_id}/confirm" if project_id else "",
                project_id=project_id,
            )
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}
