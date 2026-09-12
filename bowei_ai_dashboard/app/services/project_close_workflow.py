"""Shared query, locking, response, and notification helpers for project close workflows."""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..api_errors import CodedHTTPException
from ..domain import project_lifecycle as PL
from ..domain.project_permissions import (
    A_CANCEL_CLOSE_REQUEST,
    A_EDIT_CLOSE_REQUEST,
    A_REQUEST_CLOSE,
)
from ..services.notify import project_coach_person_ids, send as _notify
from ..services.project_access import authorize_project_action
from ..services.project_close import (
    evaluate_project_close,
    material_values,
    serialize_residual_items,
)
from ..time_utils import utc_now


class LifecycleWriter(Protocol):
    def __call__(
        self,
        project: models.Project,
        lifecycle_status: str,
        *,
        db: Session,
        project_id: int,
    ) -> str: ...


class ViewAuthorizer(Protocol):
    def __call__(
        self,
        current_user: str,
        project: models.Project,
        db: Session,
    ) -> dict: ...


CLOSE_REQUEST_STATUSES = {"pending", "approved", "rejected", "cancelled"}


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


def list_close_requests(
    *,
    project_id: int,
    status: str | None,
    current_user: str,
    db: Session,
    view_authorizer: ViewAuthorizer,
) -> list[dict]:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    view_authorizer(current_user, project, db)
    if status is not None and status not in CLOSE_REQUEST_STATUSES:
        raise HTTPException(422, "invalid close request status")
    query = db.query(models.ProjectCloseRequest).filter_by(project_id=project_id)
    if status is not None:
        query = query.filter(models.ProjectCloseRequest.status == status)
    requests = query.order_by(
        models.ProjectCloseRequest.created_at.desc(),
        models.ProjectCloseRequest.id.desc(),
    ).all()
    return [close_request_response(request, project, db) for request in requests]


def get_close_request(
    *,
    project_id: int,
    request_id: int,
    current_user: str,
    db: Session,
    view_authorizer: ViewAuthorizer,
) -> dict:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    request = close_request_for_project(project_id, request_id, db)
    view_authorizer(current_user, project, db)
    return close_request_response(request, project, db)


def create_close_request(
    *,
    project_id: int,
    payload: schemas.ProjectCloseRequestCreatePayload,
    current_user: str,
    db: Session,
    lifecycle_writer: LifecycleWriter,
) -> dict:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    access = authorize_project_action(current_user, project, A_REQUEST_CLOSE, db)
    context = access.context
    project = lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    if PL.normalize(project.status) != PL.S_ACTIVE:
        raise CodedHTTPException(409, "PROJECT_STATE_CONFLICT", "仅进行中的项目可申请结束")
    if db.query(models.ProjectCloseRequest).filter_by(project_id=project_id, status="pending").first():
        raise CodedHTTPException(409, "PROJECT_STATE_CONFLICT", "项目已有待审核的结束申请")

    material_data = payload.model_dump()
    blockers, _warnings = evaluate_project_close(db, project_id, material_data)
    if blockers:
        raise_close_blocked(blockers)

    request = models.ProjectCloseRequest(
        project_id=project_id,
        requester_person_id=context.get("person_id"),
        summary=payload.summary,
        objective_result=payload.objective_result,
        unfinished_items_json=serialize_residual_items(payload.unfinished_items),
        remaining_risks_json=serialize_residual_items(payload.remaining_risks),
        handover_plan=payload.handover_plan,
        retrospective=payload.retrospective,
        status="pending",
    )
    db.add(request)
    db.flush()
    before = close_state(request, project)
    lifecycle_writer(project, PL.S_PENDING_CLOSE, db=db, project_id=project_id)
    after = close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_create",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_requested",
        title="项目结束申请待审核",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return close_request_response(request, project, db)


def update_close_request(
    *,
    project_id: int,
    request_id: int,
    payload: schemas.ProjectCloseRequestUpdatePayload,
    current_user: str,
    db: Session,
) -> dict:
    project = lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    access = authorize_project_action(
        current_user,
        project,
        A_EDIT_CLOSE_REQUEST,
        db,
        requester_person_id=request.requester_person_id,
    )
    context = access.context
    ensure_pending_close_pair(project, request)

    current, _valid = material_values(request)
    current.update(payload.model_dump(exclude_unset=True))
    try:
        merged = schemas.ProjectCloseRequestCreatePayload.model_validate(current)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc

    before = close_state(request, project)
    request.summary = merged.summary
    request.objective_result = merged.objective_result
    request.unfinished_items_json = serialize_residual_items(merged.unfinished_items)
    request.remaining_risks_json = serialize_residual_items(merged.remaining_risks)
    request.handover_plan = merged.handover_plan
    request.retrospective = merged.retrospective
    after = close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_update",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_request_updated",
        title="项目结束材料已更新",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return close_request_response(request, project, db)


def cancel_close_request(
    *,
    project_id: int,
    request_id: int,
    current_user: str,
    db: Session,
    lifecycle_writer: LifecycleWriter,
) -> dict:
    project = lock_project_for_close(project_id, db)
    if not project:
        raise HTTPException(404, "project not found")
    request = lock_close_request(project_id, request_id, db)
    if not request:
        raise HTTPException(404, "project close request not found")
    access = authorize_project_action(
        current_user,
        project,
        A_CANCEL_CLOSE_REQUEST,
        db,
        requester_person_id=request.requester_person_id,
    )
    context = access.context
    ensure_pending_close_pair(project, request)
    before = close_state(request, project)
    request.status = "cancelled"
    request.cancelled_at = utc_now()
    lifecycle_writer(project, PL.S_ACTIVE, db=db, project_id=project_id)
    after = close_state(request, project)
    crud.log(
        db,
        current_user,
        "project_close_request_cancel",
        "project_close_request",
        request.id,
        before,
        after,
        project_id=project_id,
    )
    notify_close_people(
        db,
        project_coach_person_ids(project_id, db),
        operator_person_id=context.get("person_id"),
        ntype="project_close_cancelled",
        title="项目结束申请已取消",
        project=project,
        request=request,
    )
    db.commit()
    db.refresh(request)
    return close_request_response(request, project, db)
