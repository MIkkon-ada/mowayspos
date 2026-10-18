from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.issues import create_issue


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        models.Person(id=1, name="Member One", system_role="normal_member", is_active=True),
        models.Person(id=2, name="Member Two", system_role="normal_member", is_active=True),
        models.Person(id=3, name="Project Owner", system_role="normal_member", is_active=True),
        models.Account(username="member_one", password_hash="x", person_id=1, status="active"),
        models.Account(username="member_two", password_hash="x", person_id=2, status="active"),
        models.Project(id=1, name="Issue Idempotency", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Member One", role="member"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Member Two", role="member"),
        models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Project Owner", role="owner"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create(db, *, request_id: str | None, description: str = "风险描述", user: str = "member_one"):
    return create_issue(
        schemas.IssuePayload(
            project_id=1,
            description=description,
            client_request_id=request_id,
        ),
        current_user=user,
        db=db,
    )


def test_same_issue_create_request_returns_the_original_issue(db):
    first = _create(db, request_id="issue-request-0001")
    retry = _create(db, request_id="issue-request-0001")

    assert retry["id"] == first["id"]
    assert db.query(models.Issue).count() == 1
    assert "client_request_id" not in retry
    assert "request_payload_hash" not in retry


def test_reusing_issue_request_for_changed_content_conflicts(db):
    _create(db, request_id="issue-request-0002", description="风险一")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="issue-request-0002", description="风险二")

    assert exc.value.status_code == 409
    assert db.query(models.Issue).count() == 1


def test_another_submitter_cannot_reuse_issue_request(db):
    _create(db, request_id="issue-request-0003", user="member_one")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="issue-request-0003", user="member_two")

    assert exc.value.status_code == 409
    assert db.query(models.Issue).count() == 1


def test_issue_create_without_request_id_keeps_legacy_behavior(db):
    first = _create(db, request_id=None)
    second = _create(db, request_id=None)

    assert first["id"] != second["id"]
    assert db.query(models.Issue).count() == 2
