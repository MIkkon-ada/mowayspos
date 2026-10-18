from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.subtask_drafts import list_drafts


@pytest.fixture
def draft_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="同名草稿成员", is_active=True),
            models.Person(id=2, name="同名草稿成员", is_active=True),
            models.Account(username="member_one", password_hash="x", person_id=1, status="active"),
            models.Account(username="member_two", password_hash="x", person_id=2, status="active"),
            models.SubTaskDraft(id=1, title="本人分派草稿", proposer="author", assignee="同名草稿成员", assignee_id=1, status="pending"),
            models.SubTaskDraft(id=2, title="他人分派草稿", proposer="author", assignee="member_one", assignee_id=2, status="pending"),
            models.SubTaskDraft(id=3, title="本人旧账号草稿", proposer="member_one", assignee="member_one", assignee_id=None, status="pending"),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_global_draft_list_uses_assignee_id_when_available(draft_identity_db):
    rows = list_drafts(current_user="member_one", db=draft_identity_db)

    assert {row["id"] for row in rows} == {1, 3}
