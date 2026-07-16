"""Project close readiness checks and close-material serialization helpers."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..domain import issue_flow as IF
from ..domain import submission_status as SS
from ..domain import task_status as TS
from ..domain import project_lifecycle as PL
from ..archived_guard import require_project_not_archived


PROJECT_CLOSE_FROZEN_MESSAGE = "项目正在结束审核或已经结束，不允许执行该操作。"


def require_project_business_writable(project_id: int | None, db: Session) -> None:
    """Preserve the archived guard and freeze writes during/after close review."""
    require_project_not_archived(project_id, db)
    if project_id is None:
        return
    project = db.get(models.Project, project_id)
    if project and PL.is_close_frozen(project.status):
        raise HTTPException(409, PROJECT_CLOSE_FROZEN_MESSAGE)


def serialize_residual_items(items: list[schemas.ProjectCloseResidualItem] | list[dict]) -> str:
    values = [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in items]
    return json.dumps(values, ensure_ascii=False)


def parse_residual_items(value: str | None) -> tuple[list[dict], bool]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], False
    if not isinstance(parsed, list):
        return [], False
    return parsed, True


def material_values(source: models.ProjectCloseRequest | dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if isinstance(source, models.ProjectCloseRequest):
        unfinished_items, unfinished_valid = parse_residual_items(source.unfinished_items_json)
        remaining_risks, risks_valid = parse_residual_items(source.remaining_risks_json)
        return (
            {
                "summary": source.summary,
                "objective_result": source.objective_result,
                "unfinished_items": unfinished_items,
                "remaining_risks": remaining_risks,
                "handover_plan": source.handover_plan,
                "retrospective": source.retrospective,
            },
            unfinished_valid and risks_valid,
        )
    return dict(source), True


def validate_materials(source: models.ProjectCloseRequest | dict[str, Any]) -> bool:
    values, storage_valid = material_values(source)
    if not storage_valid:
        return False
    try:
        schemas.ProjectCloseRequestCreatePayload.model_validate(values)
    except ValidationError:
        return False
    return True


def _human_result(row: models.UpdateSubmission) -> dict[str, Any]:
    try:
        data = json.loads(row.human_result_json or row.ai_result_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _has_card_state(row: models.UpdateSubmission, expected: str) -> bool:
    reports = _human_result(row).get("task_reports")
    if not isinstance(reports, list):
        return False
    return any(
        isinstance(report, dict)
        and str(report.get("confirmation_status") or "").strip() == expected
        for report in reports
    )


def _item(code: str, count: int, message: str) -> dict[str, Any]:
    return {"code": code, "count": count, "message": message.format(count=count)}


def evaluate_project_close(
    db: Session,
    project_id: int,
    materials: models.ProjectCloseRequest | dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    submissions = (
        db.query(models.UpdateSubmission)
        .filter(models.UpdateSubmission.project_id == project_id)
        .all()
    )
    pending_ids = {
        row.id for row in submissions if (row.confirm_status or "").strip() in SS.ALL_ACTIVE
    }
    coordinator_ids = {
        row.id
        for row in submissions
        if (row.confirm_status or "").strip() in SS.WAITING_COORDINATOR_FEEDBACK
        or _has_card_state(row, "transferred_to_coordinator")
    }
    coach_ids = {
        row.id
        for row in submissions
        if (row.confirm_status or "").strip() in SS.WAITING_CEO_DECISION
        or _has_card_state(row, "pending_ceo_decision")
    }
    if pending_ids:
        blockers.append(
            _item("pending_confirmations", len(pending_ids), "仍有 {count} 条提交尚未完成确认流程")
        )
    if coordinator_ids:
        blockers.append(
            _item("waiting_coordinator", len(coordinator_ids), "仍有 {count} 条提交或任务卡等待统筹反馈")
        )
    if coach_ids:
        blockers.append(
            _item("waiting_project_coach", len(coach_ids), "仍有 {count} 条提交或任务卡等待项目企业教练决策")
        )

    decision_count = sum(
        1
        for issue in db.query(models.Issue).filter(models.Issue.project_id == project_id).all()
        if IF.normalize_type(issue.issue_type) == IF.TYPE_DECISION
        and IF.normalize_status(issue.status) not in {IF.STATUS_RESOLVED, IF.STATUS_CLOSED}
    )
    if decision_count:
        blockers.append(
            _item("pending_decision_issues", decision_count, "仍有 {count} 个待决策重大问题")
        )

    achievement_count = (
        db.query(models.AchievementSubmission)
        .filter(
            models.AchievementSubmission.project_id == project_id,
            models.AchievementSubmission.status == "待确认",
        )
        .count()
    )
    if achievement_count:
        blockers.append(
            _item("pending_achievement_submissions", achievement_count, "仍有 {count} 项成果待审核")
        )

    member_change_count = (
        db.query(models.MemberChangeRequest)
        .filter(
            models.MemberChangeRequest.project_id == project_id,
            models.MemberChangeRequest.status == "pending",
        )
        .count()
    )
    if member_change_count:
        blockers.append(
            _item("pending_member_change_requests", member_change_count, "仍有 {count} 项成员变更待处理")
        )

    if not validate_materials(materials):
        blockers.append(_item("incomplete_close_materials", 1, "结束材料不完整或已损坏"))

    unfinished_count = (
        db.query(models.SubTask)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(models.Task.project_id == project_id, models.SubTask.is_deleted.is_(False))
        .all()
    )
    unfinished_count = sum(1 for row in unfinished_count if TS.normalize(row.status) not in TS.TERMINAL)
    if unfinished_count:
        warnings.append(
            _item("unfinished_key_tasks", unfinished_count, "仍有 {count} 个关键任务未完成")
        )

    open_issue_count = sum(
        1
        for issue in db.query(models.Issue).filter(models.Issue.project_id == project_id).all()
        if IF.normalize_type(issue.issue_type) != IF.TYPE_DECISION
        and IF.normalize_status(issue.status) not in {IF.STATUS_RESOLVED, IF.STATUS_CLOSED}
    )
    if open_issue_count:
        warnings.append(
            _item("open_non_decision_issues", open_issue_count, "仍有 {count} 个普通问题未关闭")
        )

    return blockers, warnings
