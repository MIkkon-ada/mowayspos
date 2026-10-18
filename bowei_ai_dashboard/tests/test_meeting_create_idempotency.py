from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.meetings import create_meeting


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            models.Project(id=1, name="会议幂等项目", status="active", is_active=True),
            models.Person(id=1, name="项目成员一", is_active=True),
            models.Person(id=2, name="项目成员二", is_active=True),
            models.Account(username="member_one", password_hash="x", person_id=1, status="active"),
            models.Account(username="member_two", password_hash="x", person_id=2, status="active"),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="项目成员一", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="项目成员二", role="member"),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create(db, *, request_id: str | None, title: str = "项目周会", user: str = "member_one", analysis_id: int | None = None):
    return create_meeting(
        schemas.MeetingPayload(
            project_id=1,
            analysis_id=analysis_id,
            meeting_type="项目进展会",
            title=title,
            meeting_date="2026-10-08",
            summary="周会纪要",
            client_request_id=request_id,
        ),
        current_user=user,
        db=db,
    )


def test_same_meeting_create_request_returns_original_without_duplicate_revision(db):
    first = _create(db, request_id="meeting-request-001")
    retry = _create(db, request_id="meeting-request-001")

    assert retry["id"] == first["id"]
    assert db.query(models.Meeting).count() == 1
    assert db.query(models.MeetingRevision).filter_by(meeting_id=first["id"]).count() == 1
    assert "client_request_id" not in retry
    assert "request_payload_hash" not in retry


def test_reusing_meeting_request_for_changed_content_conflicts(db):
    _create(db, request_id="meeting-request-002", title="周会一")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="meeting-request-002", title="周会二")

    assert exc.value.status_code == 409
    assert db.query(models.Meeting).count() == 1


def test_another_project_member_cannot_reuse_meeting_request(db):
    _create(db, request_id="meeting-request-003", user="member_one")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="meeting-request-003", user="member_two")

    assert exc.value.status_code == 409
    assert db.query(models.Meeting).count() == 1


def test_meeting_create_without_request_id_keeps_legacy_behavior(db):
    first = _create(db, request_id=None)
    second = _create(db, request_id=None)

    assert first["id"] != second["id"]
    assert db.query(models.Meeting).count() == 2


def test_retry_returns_meeting_after_analysis_draft_was_attached(db):
    db.add(models.MeetingChangeSet(
        id=1,
        project_id=1,
        created_by_person_id=1,
        transcript_hash="a" * 64,
        snapshot_json="{}",
        result_json="{}",
        status="draft",
    ))
    db.commit()

    first = _create(db, request_id="meeting-request-004", analysis_id=1)
    retry = _create(db, request_id="meeting-request-004", analysis_id=1)

    change_set = db.get(models.MeetingChangeSet, 1)
    assert retry["id"] == first["id"]
    assert change_set.meeting_id == first["id"]
    assert change_set.status == "attached"
    assert db.query(models.Meeting).count() == 1
