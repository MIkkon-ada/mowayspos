from __future__ import annotations

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
    get_project_close_request,
    reject_project_close_request,
    update_project_close_request,
)


def _seed():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    roles = [
        (1, "Owner", "owner", "normal_member"),
        (2, "Other Owner", "other_owner", "normal_member"),
        (3, "Coach", "coach", "normal_member"),
        (4, "Coordinator", "coordinator", "normal_member"),
        (5, "Member", "member", "normal_member"),
        (6, "Company CEO", "company_ceo", "company_ceo"),
        (7, "Outsider", "outsider", "normal_member"),
    ]
    for pid, name, username, system_role in roles:
        db.add(models.Person(id=pid, name=name, system_role=system_role, is_active=True))
        db.add(models.Account(username=username, password_hash="x", person_id=pid, status="active"))
    db.add(models.Project(id=1, name="Project", status="active", is_active=True))
    for pid, role in [(1, "owner"), (2, "owner"), (3, "project_ceo"), (4, "coordinator"), (5, "member")]:
        db.add(models.ProjectMember(project_id=1, person_id=pid, person_name_snapshot="", role=role))
    db.commit()
    return db


def _payload():
    return schemas.ProjectCloseRequestCreatePayload(
        summary="Done",
        objective_result="Done",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="Done",
        retrospective="Done",
    )


@pytest.mark.parametrize(
    "username,allowed",
    [
        ("owner", True),
        ("moways", True),
        ("other_owner", True),
        ("coach", False),
        ("coordinator", False),
        ("member", False),
        ("company_ceo", False),
    ],
)
def test_create_permission_matrix(username: str, allowed: bool):
    db = _seed()
    if allowed:
        assert create_project_close_request(1, _payload(), current_user=username, db=db)["status"] == "pending"
    else:
        with pytest.raises(HTTPException) as exc:
            create_project_close_request(1, _payload(), current_user=username, db=db)
        assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "username,allowed",
    [
        ("owner", True),
        ("other_owner", True),
        ("coach", True),
        ("coordinator", True),
        ("member", True),
        ("company_ceo", True),
        ("moways", True),
        ("outsider", False),
    ],
)
def test_read_permission_matrix(username: str, allowed: bool):
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    if allowed:
        assert get_project_close_request(1, request["id"], current_user=username, db=db)["id"] == request["id"]
    else:
        with pytest.raises(HTTPException) as exc:
            get_project_close_request(1, request["id"], current_user=username, db=db)
        assert exc.value.status_code == 403


def test_only_original_requester_owner_or_superadmin_can_edit_and_cancel():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)

    for username in ("other_owner", "coach", "company_ceo", "coordinator", "member"):
        with pytest.raises(HTTPException) as exc:
            update_project_close_request(
                1,
                request["id"],
                schemas.ProjectCloseRequestUpdatePayload(summary="No"),
                current_user=username,
                db=db,
            )
        assert exc.value.status_code == 403

    assert update_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseRequestUpdatePayload(summary="Root edit"),
        current_user="moways",
        db=db,
    )["summary"] == "Root edit"
    assert cancel_project_close_request(1, request["id"], current_user="owner", db=db)["status"] == "cancelled"


def test_only_project_coach_or_superadmin_can_review_and_reject_requires_comment():
    db = _seed()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)

    for username in ("owner", "other_owner", "company_ceo", "coordinator", "member"):
        with pytest.raises(HTTPException) as exc:
            approve_project_close_request(
                1,
                request["id"],
                schemas.ProjectCloseReviewPayload(),
                current_user=username,
                db=db,
            )
        assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        reject_project_close_request(
            1,
            request["id"],
            schemas.ProjectCloseReviewPayload(review_comment="  "),
            current_user="coach",
            db=db,
        )
    assert exc.value.status_code == 422

    assert approve_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseReviewPayload(),
        current_user="coach",
        db=db,
    )["status"] == "approved"
