"""Shared query, locking, response, and notification helpers for project close workflows."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..api_errors import CodedHTTPException
from ..domain import project_lifecycle as PL
from ..services.notify import send as _notify
from ..services.project_close import evaluate_project_close, material_values


def project_close_project_lock_statement(project_id: int):
    return (
        select(models.Project)
        .where(models.Project.id == project_id)
        .with_for_update()
    )


def project_close_request_lock_statement(project_id: int, request_id: int):
    return (
        select(models.ProjectCloseRequest)
        .where(
            models.ProjectCloseRequest.id == request_id,
            models.ProjectCloseRequest.project_id == project_id,
        )
        .with_for_update()
    )


def lock_project_for_close(project_id: int, db: Session) -> models.Project | None:
    statement = project_close_project_lock_statement(project_id).execution_options(
        populate_existing=True
    )
    return db.execute(statement).scalar_one_or_none()


def lock_close_request(
    project_id: int,
    request_id: int,
    db: Session,
) -> models.ProjectCloseRequest | None:
    statement = project_close_request_lock_statement(
        project_id,
        request_id,
    ).execution_options(populate_existing=True)
    return db.execute(statement).scalar_one_or_none()


def close_request_for_project(
    project_id: int,
    request_id: int,
    db: Session,
) -> models.ProjectCloseRequest:
    request = db.get(models.ProjectCloseRequest, request_id)
    if not request or request.project_id != project_id:
        raise HTTPException(404, "project close request not found")
    return request


def close_state(request: models.ProjectCloseRequest, project: models.Project) -> dict:
    values, materials_valid = material_values(request)
    return {
        "request_status": request.status,
        "project_status": project.status,
        "reviewer_person_id": request.reviewer_person_id,
        "review_comment": request.review_comment or "",
        "summary": values["summary"],
        "objective_result": values["objective_result"],
        "unfinished_items": values["unfinished_items"],
        "remaining_risks": values["remaining_risks"],
        "handover_plan": values["handover_plan"],
        "retrospective": values["retrospective"],
        "materials_valid": materials_valid,
    }


def close_datetime(value) -> str | None:
    return value.isoformat(timespec="seconds") + "Z" if value else None


def close_request_response(
    request: models.ProjectCloseRequest,
    project: models.Project,
    db: Session,
) -> dict:
    values, _storage_valid = material_values(request)
    requester = db.get(models.Person, request.requester_person_id) if request.requester_person_id else None
    reviewer = db.get(models.Person, request.reviewer_person_id) if request.reviewer_person_id else None
    blockers, warnings = evaluate_project_close(db, project.id, request)
    return {
        "id": request.id,
        "project_id": project.id,
        "project_name": project.name,
        "project_status": project.status,
        "requester_person_id": request.requester_person_id,
        "requester_name": requester.name if requester else "",
        "summary": request.summary,
        "objective_result": request.objective_result,
        "unfinished_items": values["unfinished_items"],
        "remaining_risks": values["remaining_risks"],
        "handover_plan": request.handover_plan,
        "retrospective": request.retrospective,
        "status": request.status,
        "reviewer_person_id": request.reviewer_person_id,
        "reviewer_name": reviewer.name if reviewer else "",
        "review_comment": request.review_comment or "",
        "created_at": close_datetime(request.created_at),
        "updated_at": close_datetime(request.updated_at),
        "reviewed_at": close_datetime(request.reviewed_at),
        "cancelled_at": close_datetime(request.cancelled_at),
        "blockers": blockers,
        "warnings": warnings,
    }


def close_link(project_id: int, request_id: int) -> str:
    return f"/home/projects?projectId={project_id}&closeRequestId={request_id}"


def notify_close_people(
    db: Session,
    recipient_ids: list[int],
    *,
    operator_person_id: int | None,
    ntype: str,
    title: str,
    project: models.Project,
    request: models.ProjectCloseRequest,
) -> None:
    seen: set[int] = set()
    for recipient_id in recipient_ids:
        if not recipient_id or recipient_id == operator_person_id or recipient_id in seen:
            continue
        seen.add(recipient_id)
        _notify(
            db,
            recipient_id=recipient_id,
            ntype=ntype,
            title=title,
            body=f"项目《{project.name}》结束申请状态已更新。",
            link=close_link(project.id, request.id),
            project_id=project.id,
        )


def ensure_pending_close_pair(
    project: models.Project,
    request: models.ProjectCloseRequest,
) -> None:
    if request.status != "pending" or PL.normalize(project.status) != PL.S_PENDING_CLOSE:
        raise CodedHTTPException(409, "PROJECT_STATE_CONFLICT", "结束申请已不处于待审核状态")


def raise_close_blocked(blockers: list[dict]) -> None:
    raise HTTPException(409, {"code": "PROJECT_CLOSE_BLOCKED", "blockers": blockers})
