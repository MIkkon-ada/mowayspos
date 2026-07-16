from __future__ import annotations

import json

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.projects import (
    approve_project_close_request,
    cancel_project_close_request,
    create_project_close_request,
    reject_project_close_request,
    update_project_close_request,
)


def _seed():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for pid, name, username in [
        (1, "Owner", "owner"),
        (2, "Other Owner", "other_owner"),
        (3, "Coach", "coach"),
        (4, "Member", "member"),
    ]:
        db.add(models.Person(id=pid, name=name, system_role="normal_member", is_active=True))
        db.add(models.Account(username=username, password_hash="x", person_id=pid, status="active"))
    db.add(models.Project(id=1, name="Project", status="active", is_active=True))
    for pid, role in [(1, "owner"), (2, "owner"), (3, "project_ceo"), (4, "member")]:
        db.add(models.ProjectMember(project_id=1, person_id=pid, person_name_snapshot="", role=role))
    db.commit()
    return db


def _payload(summary: str = "Done"):
    return schemas.ProjectCloseRequestCreatePayload(
        summary=summary,
        objective_result="Done",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="Done",
        retrospective="Done",
    )


def _assert_notification(row: models.Notification, ntype: str, recipient_id: int, request_id: int):
    assert row.type == ntype
    assert row.recipient_id == recipient_id
    assert row.project_id == 1
    assert row.link == f"/home/projects?projectId=1&closeRequestId={request_id}"


def _assert_log(row: models.OperationLog, action: str, request_id: int):
    assert row.action == action
    assert row.project_id == 1
    assert row.target_type == "project_close_request"
    assert row.target_id == request_id
    before = json.loads(row.before_json)
    after = json.loads(row.after_json)
    for field in ("request_status", "project_status", "reviewer_person_id", "review_comment"):
        assert field in before
        assert field in after


def test_create_update_cancel_emit_exact_coach_notifications_and_logs():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    update_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseRequestUpdatePayload(summary="Updated"),
        current_user="owner",
        db=db,
    )
    cancel_project_close_request(1, request["id"], current_user="owner", db=db)

    notifications = db.query(models.Notification).order_by(models.Notification.id).all()
    assert [row.type for row in notifications] == [
        "project_close_requested",
        "project_close_request_updated",
        "project_close_cancelled",
    ]
    for row, ntype in zip(notifications, [
        "project_close_requested",
        "project_close_request_updated",
        "project_close_cancelled",
    ]):
        _assert_notification(row, ntype, 3, request["id"])

    logs = db.query(models.OperationLog).order_by(models.OperationLog.id).all()
    assert [row.action for row in logs] == [
        "project_close_request_create",
        "project_close_request_update",
        "project_close_request_cancel",
    ]
    for row, action in zip(logs, [
        "project_close_request_create",
        "project_close_request_update",
        "project_close_request_cancel",
    ]):
        _assert_log(row, action, request["id"])


def test_approve_notifies_all_unique_members_except_operator_and_logs_transition():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    db.query(models.Notification).delete()
    db.commit()

    approve_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseReviewPayload(review_comment="Approved"),
        current_user="coach",
        db=db,
    )

    notifications = db.query(models.Notification).order_by(models.Notification.recipient_id).all()
    assert [row.recipient_id for row in notifications] == [1, 2, 4]
    for row in notifications:
        _assert_notification(row, "project_close_approved", row.recipient_id, request["id"])

    log = db.query(models.OperationLog).filter_by(action="project_close_request_approve").one()
    _assert_log(log, "project_close_request_approve", request["id"])
    assert json.loads(log.before_json)["project_status"] == "pending_close"
    assert json.loads(log.after_json)["project_status"] == "ended"


def test_reject_notifies_requester_and_true_owners_without_duplicates():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    db.query(models.Notification).delete()
    db.commit()

    reject_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseReviewPayload(review_comment="Revise"),
        current_user="coach",
        db=db,
    )

    notifications = db.query(models.Notification).order_by(models.Notification.recipient_id).all()
    assert [row.recipient_id for row in notifications] == [1, 2]
    for row in notifications:
        _assert_notification(row, "project_close_rejected", row.recipient_id, request["id"])


def test_repeated_terminal_action_has_no_duplicate_log_or_notification():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    cancel_project_close_request(1, request["id"], current_user="owner", db=db)
    log_count = db.query(models.OperationLog).count()
    notification_count = db.query(models.Notification).count()

    with pytest.raises(HTTPException) as exc:
        cancel_project_close_request(1, request["id"], current_user="owner", db=db)
    assert exc.value.status_code == 409
    assert db.query(models.OperationLog).count() == log_count
    assert db.query(models.Notification).count() == notification_count
