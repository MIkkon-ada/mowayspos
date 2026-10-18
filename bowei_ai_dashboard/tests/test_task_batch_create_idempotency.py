from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.tasks import batch_create


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
        models.Project(id=1, name="Batch Idempotency", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner One", role="owner"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Owner Two", role="owner"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _batch(db, *, request_id: str | None, titles: tuple[str, ...] = ("重点工作一", "重点工作二"), user: str = "owner_one"):
    return batch_create(
        schemas.TaskBatchCreateRequest(
            project_id=1,
            client_request_id=request_id,
            tasks=[schemas.TaskDraft(key_task=title) for title in titles],
        ),
        current_user=user,
        db=db,
    )


def test_same_batch_create_request_returns_the_original_rows_in_order(db):
    first = _batch(db, request_id="outline-batch-request-001")
    retry = _batch(db, request_id="outline-batch-request-001")

    assert [row["id"] for row in retry] == [row["id"] for row in first]
    assert [row["key_task"] for row in retry] == ["重点工作一", "重点工作二"]
    assert db.query(models.Task).count() == 2


def test_reusing_batch_request_for_changed_drafts_conflicts(db):
    _batch(db, request_id="outline-batch-request-002")

    with pytest.raises(HTTPException) as exc:
        _batch(db, request_id="outline-batch-request-002", titles=("重点工作一", "修改后的重点工作"))

    assert exc.value.status_code == 409
    assert db.query(models.Task).count() == 2


def test_another_owner_cannot_reuse_batch_request(db):
    _batch(db, request_id="outline-batch-request-003", user="owner_one")

    with pytest.raises(HTTPException) as exc:
        _batch(db, request_id="outline-batch-request-003", user="owner_two")

    assert exc.value.status_code == 409
    assert db.query(models.Task).count() == 2


def test_batch_create_without_request_id_keeps_legacy_behavior(db):
    first = _batch(db, request_id=None)
    second = _batch(db, request_id=None)

    assert len(first) == len(second) == 2
    assert {row["id"] for row in first}.isdisjoint({row["id"] for row in second})
    assert db.query(models.Task).count() == 4
