from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.meetings import _fetch_member_context


@pytest.fixture
def meeting_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_meeting_ai_context_does_not_mix_tasks_for_duplicate_member_names(meeting_identity_db):
    db = meeting_identity_db
    db.add_all(
        [
            models.Person(id=1, name="同名汇报人", is_active=True),
            models.Person(id=2, name="同名汇报人", is_active=True),
            models.Project(id=1, name="会议身份项目", status="active", is_active=True),
            models.Task(id=1, project_id=1, key_task="甲的任务", owner="同名汇报人", owner_id=1, status="进行中"),
            models.Task(id=2, project_id=1, key_task="乙的任务", owner="同名汇报人", owner_id=2, status="进行中"),
        ]
    )
    db.commit()

    result = _fetch_member_context("同名汇报人", 1, db)

    assert result["tasks"] == []
    assert result["last_next_steps"] == []


def test_meeting_ai_context_prefers_task_owner_person_id(meeting_identity_db):
    db = meeting_identity_db
    db.add_all(
        [
            models.Person(id=1, name="唯一汇报人", is_active=True),
            models.Person(id=2, name="其他人员", is_active=True),
            models.Project(id=1, name="会议身份项目", status="active", is_active=True),
            models.Task(id=1, project_id=1, key_task="本人任务", owner="唯一汇报人", owner_id=1, status="进行中"),
            models.Task(id=2, project_id=1, key_task="他人误记名任务", owner="唯一汇报人", owner_id=2, status="进行中"),
        ]
    )
    db.commit()

    result = _fetch_member_context("唯一汇报人", 1, db)

    assert [task["task"] for task in result["tasks"]] == ["本人任务"]
