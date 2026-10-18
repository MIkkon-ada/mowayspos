from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.tasks import create_task


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        models.Person(id=1, name="Owner One", system_role="normal_member", is_active=True),
        models.Person(id=2, name="Owner Two", system_role="normal_member", is_active=True),
        models.Account(username="owner_one", password_hash="x", person_id=1, status="active"),
        models.Account(username="owner_two", password_hash="x", person_id=2, status="active"),
        models.Project(id=1, name="Task Idempotency", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner One", role="owner"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Owner Two", role="owner"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create(db, *, request_id: str | None, title: str = "重点工作", user: str = "owner_one"):
    return create_task(
        schemas.TaskPayload(
            project_id=1,
            key_task=title,
            client_request_id=request_id,
        ),
        current_user=user,
        db=db,
    )


def test_same_task_create_request_returns_the_existing_task(db):
    first = _create(db, request_id="task-request-0001")
    retry = _create(db, request_id="task-request-0001")

    assert retry["id"] == first["id"]
    assert db.query(models.Task).count() == 1
    assert "client_request_id" not in retry
    assert "request_payload_hash" not in retry


def test_reusing_task_create_request_for_different_content_conflicts(db):
    _create(db, request_id="task-request-0002", title="重点工作一")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="task-request-0002", title="重点工作二")

    assert exc.value.status_code == 409
    assert db.query(models.Task).count() == 1


def test_another_owner_cannot_reuse_task_create_request(db):
    _create(db, request_id="task-request-0003", user="owner_one")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="task-request-0003", user="owner_two")

    assert exc.value.status_code == 409
    assert db.query(models.Task).count() == 1


def test_task_creates_without_request_id_keep_legacy_behavior(db):
    first = _create(db, request_id=None)
    second = _create(db, request_id=None)

    assert first["id"] != second["id"]
    assert db.query(models.Task).count() == 2
