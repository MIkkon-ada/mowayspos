from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.achievements import create_achievement


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            models.Project(id=1, name="成果幂等项目", status="active", is_active=True),
            models.Person(id=1, name="负责人一", is_active=True),
            models.Person(id=2, name="负责人二", is_active=True),
            models.Account(username="owner_one", password_hash="x", person_id=1, status="active"),
            models.Account(username="owner_two", password_hash="x", person_id=2, status="active"),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="负责人一", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="负责人二", role="owner"),
            models.Task(id=10, project_id=1, key_task="完成项目成果"),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create(db, *, request_id: str | None, name: str = "成果清单", user: str = "owner_one"):
    return create_achievement(
        schemas.AchievementPayload(
            project_id=1,
            name=name,
            achievement_type="文档",
            related_task_id=10,
            owner="负责人一",
            status="已入库",
            client_request_id=request_id,
        ),
        current_user=user,
        db=db,
    )


def test_same_manual_achievement_create_request_returns_original(db):
    first = _create(db, request_id="achievement-request-001")
    retry = _create(db, request_id="achievement-request-001")

    assert retry["id"] == first["id"]
    assert db.query(models.Achievement).count() == 1
    assert "client_request_id" not in retry
    assert "request_payload_hash" not in retry


def test_reusing_achievement_request_for_changed_content_conflicts(db):
    _create(db, request_id="achievement-request-002", name="成果一")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="achievement-request-002", name="成果二")

    assert exc.value.status_code == 409
    assert db.query(models.Achievement).count() == 1


def test_another_project_owner_cannot_reuse_achievement_request(db):
    _create(db, request_id="achievement-request-003", user="owner_one")

    with pytest.raises(HTTPException) as exc:
        _create(db, request_id="achievement-request-003", user="owner_two")

    assert exc.value.status_code == 409
    assert db.query(models.Achievement).count() == 1


def test_manual_achievement_without_request_id_keeps_legacy_behavior(db):
    first = _create(db, request_id=None)
    second = _create(db, request_id=None)

    assert first["id"] != second["id"]
    assert db.query(models.Achievement).count() == 2
