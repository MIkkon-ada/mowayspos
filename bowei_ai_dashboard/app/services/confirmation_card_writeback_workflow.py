"""Service-owned final writeback for a single confirmation task card."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain import issue_flow as IF
from ..domain import issue_type as IT
from ..domain import source_type as ST
from ..domain import submission_result_type as RT
from ..domain import submission_status as SS
from ..domain import task_status as TS
from ..permissions import get_user_context_from_db
from ..routers.subtasks import _sync_parent_task_status
from ..services import workflow as W
from ..services.confirmation_review_workflow import (
    load_submission,
    require_confirmation_center,
    require_owner_style_actor,
    require_submission_writable,
    submission_project_context,
    submission_project_name,
)
from ..time_utils import utc_now


_CARD_OWNER_ACTIONABLE = frozenset({"", "pending", "ceo_decided", "coordinator_given"})
_CARD_WORKFLOW_FIELDS = frozenset({
    "confirmation_status", "confirmation_note", "confirmation_operator", "confirmation_at",
    "coordinator_request_note", "coordinator_request_operator", "coordinator_requested_at",
    "coordinator_note", "coordinator_operator", "coordinator_feedback_at",
    "ceo_note", "ceo_operator", "ceo_decided_at",
})


def _task_reports(data: dict) -> list[dict]:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        raise HTTPException(400, "task_reports must be a list")
    return reports


def _get_task_card(data: dict, card_index: int) -> tuple[list[dict], dict]:
    reports = _task_reports(data)
    if card_index < 0 or card_index >= len(reports):
        raise HTTPException(404, "task card not found")
    report = reports[card_index]
    if not isinstance(report, dict):
        raise HTTPException(400, "task card is not an object")
    return reports, report


def _card_confirmation_status(report: dict) -> str:
    return (report.get("confirmation_status") or "").strip()


def _require_card_owner_actionable(report: dict) -> None:
    if _card_confirmation_status(report) not in _CARD_OWNER_ACTIONABLE:
        raise HTTPException(409, "task card cannot be processed in its current state")


def _merge_card_confirmation_payload(data: dict, human_result: dict | None) -> dict:
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


def _mark_task_card(row: models.UpdateSubmission, data: dict, card_index: int, status: str, operator: str) -> None:
    reports, report = _get_task_card(data, card_index)
    report.update({
        "confirmation_status": status,
        "confirmation_operator": operator,
        "confirmation_note": "",
        "confirmation_at": utc_now().isoformat(),
    })
    reports[card_index] = report
    data["task_reports"] = reports
    row.human_result_json = json.dumps(data, ensure_ascii=False)


def _all_task_cards_confirmed(data: dict) -> bool:
    reports = _task_reports(data)
    return bool(reports) and all(
        isinstance(report, dict) and report.get("confirmation_status") == "confirmed"
        for report in reports
    )


def _parse_subtask_issue(item: object) -> dict | None:
    if isinstance(item, dict):
        description = (item.get("description") or "").strip()
        if description:
            return {"issue_type": IT.normalize(item.get("issue_type")), "description": description, "priority": str(item.get("priority") or "中")}
    return None


def _storage_issue_type(issue_type: str | None) -> str:
    labels = {IT.TYPE_ISSUE: IF.TYPE_ISSUE, IT.TYPE_RISK: IF.TYPE_RISK, IT.TYPE_COORDINATION: IF.TYPE_COORDINATE, IT.TYPE_DECISION: IF.TYPE_DECISION, IT.TYPE_UNKNOWN: IF.TYPE_ISSUE}
    return labels.get(IT.normalize(issue_type), IF.TYPE_ISSUE)


def _issue_status_for(issue_type: str | None) -> str:
    return IF.STATUS_PENDING_DECISION if IT.is_decision(issue_type) else IF.STATUS_PENDING


def _write_single_task_report(db: Session, row: models.UpdateSubmission, data: dict, report: dict, operator: str, project_id: int | None, project_name: str, now: datetime) -> int | None:
    task_id = row.related_task_id
    item_type = report.get("result_type")
    if item_type == RT.TYPE_SUGGEST_NEW_SUBTASK:
        parent_task_id = report.get("parent_task_id")
        if not parent_task_id:
            raise HTTPException(422, "suggest_new_subtask missing parent_task_id")
        parent = db.get(models.Task, int(parent_task_id))
        if not parent or parent.is_deleted:
            return task_id
        subtask = models.SubTask(
            task_id=parent.id,
            title=str(report.get("title") or "new subtask")[:200],
            assignee=str(report.get("assignee") or row.submitter or ""),
            plan_time=str(report.get("plan_end") or ""),
            status=TS.S_IN_PROGRESS,
            source_submission_id=row.id,
        )
        db.add(subtask)
        db.flush()
        _sync_parent_task_status(parent, db, operator)
        task_id = parent.id
        row.related_task_id = parent.id
        if data.get("write_task_reports_achievements", True):
            for item in report.get("achievements") or []:
                if isinstance(item, dict) and item.get("name"):
                    payload = dict(item)
                    payload.setdefault("special_project", project_name)
                    payload.setdefault("owner", row.submitter or "")
                    achievement = W.fulfill_or_create_achievement(db, payload, row.source_type, parent.id, payload.get("special_project") or project_name, submission_id=row.id)
                    if achievement:
                        achievement.confirmed_by = operator
                        achievement.confirmed_at = now
                        achievement.related_subtask_id = subtask.id
                        if project_id and not achievement.project_id:
                            achievement.project_id = project_id
        crud.log(db, operator, "confirmation_card_create_subtask", "subtask", subtask.id, {}, {"title": subtask.title, "task_id": parent.id, "from_submission": row.id}, project_id=project_id)
        return task_id
    if item_type not in (RT.TYPE_SUBTASK_PROGRESS, RT.TYPE_SUBTASK_COMPLETE, None):
        return task_id
    if item_type is None and report.get("type", "progress") != "progress":
        return task_id
    matched_id = report.get("matched_subtask_id")
    if not matched_id:
        return task_id
    subtask = db.get(models.SubTask, int(matched_id))
    if not subtask or subtask.is_deleted:
        raise HTTPException(422, "关键任务不存在或已删除。")
    crud.validate_subtask_link(db, project_id, subtask.task_id, int(matched_id))
    completed = (report.get("completed") or "").strip()
    if completed:
        subtask.notes = f"{subtask.notes or ''}\n[{now.strftime('%Y-%m-%d')}] {completed}".strip()
    if item_type == RT.TYPE_SUBTASK_COMPLETE:
        subtask.status = TS.S_COMPLETED
    elif item_type is None and report.get("status_update"):
        subtask.status = str(report["status_update"]).strip()[:20]
    subtask.source_submission_id = row.id
    parent = db.get(models.Task, subtask.task_id)
    if parent:
        _sync_parent_task_status(parent, db, operator)
        task_id = parent.id
        row.related_task_id = parent.id
    if data.get("write_task_reports_achievements", True):
        for item in report.get("achievements") or []:
            if isinstance(item, dict) and item.get("name"):
                payload = dict(item)
                payload.setdefault("special_project", project_name)
                payload.setdefault("owner", row.submitter or "")
                achievement = W.fulfill_or_create_achievement(db, payload, row.source_type, task_id, payload.get("special_project") or project_name, submission_id=row.id)
                if achievement:
                    achievement.confirmed_by = operator
                    achievement.confirmed_at = now
                    achievement.related_subtask_id = int(matched_id)
                    if project_id and not achievement.project_id:
                        achievement.project_id = project_id
    if data.get("write_task_reports_issues", True):
        for item in report.get("subtask_issues") or []:
            parsed = _parse_subtask_issue(item)
            if parsed:
                issue = models.Issue(issue_type=_storage_issue_type(parsed["issue_type"]), description=parsed["description"], owner=row.submitter or "", priority=parsed["priority"], status=_issue_status_for(parsed["issue_type"]), special_project=project_name, source_type=ST.normalize(row.source_type or "人工录入"), confirmed_by=operator, source_submission_id=row.id, related_task_id=subtask.task_id, related_subtask_id=int(matched_id))
                if project_id:
                    issue.project_id = project_id
                db.add(issue)
    return task_id


def confirm_task_card(*, submission_id: int, card_index: int, payload: schemas.ConfirmRequest, current_user: str, db: Session) -> dict:
    row = load_submission(db, submission_id)
    context = get_user_context_from_db(current_user or payload.operator, db)
    require_submission_writable(row, context, db)
    require_confirmation_center(context)
    require_owner_style_actor(context, row, db)
    W.require_submission_status(row, SS.OWNER_ACTIONABLE)
    before = crud.to_dict(row)
    persisted_data = W.submission_result(row)
    _, persisted_report = _get_task_card(persisted_data, card_index)
    _require_card_owner_actionable(persisted_report)
    data = _merge_card_confirmation_payload(persisted_data, payload.human_result)
    _, report = _get_task_card(data, card_index)
    project_id = submission_project_context(db, row, json_payload=data)["project_id"]
    now = utc_now()
    task_id = _write_single_task_report(db, row, data, report, payload.operator, project_id, submission_project_name(db, row, json_payload=data), now)
    _mark_task_card(row, data, card_index, "confirmed", payload.operator)
    if _all_task_cards_confirmed(data):
        row.confirm_status = SS.S_CONFIRMED
        row.confirmed_by = payload.operator
        row.confirmed_at = now
    else:
        row.confirm_status = SS.S_PENDING_OWNER
    crud.log(db, payload.operator, "confirmation_card_approve", "confirmation", row.id, before, {"card_index": card_index, "task_id": task_id}, project_id=project_id)
    db.commit()
    return {"ok": True, "submission": crud.to_dict(row)}
