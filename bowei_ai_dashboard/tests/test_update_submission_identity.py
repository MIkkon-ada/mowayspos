from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.updates import _find_recent_duplicate_submission
from app.time_utils import utc_now


@pytest.fixture
def update_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="汇报人甲", is_active=True),
            models.Person(id=2, name="汇报人甲", is_active=True),
            models.Person(id=3, name="alice", is_active=True),
            models.Account(username="alice", password_hash="x", person_id=1, status="active"),
            models.Account(username="bob", password_hash="x", person_id=2, status="active"),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _find(db, context):
    return _find_recent_duplicate_submission(
        db,
        context=context,
        current_user="alice",
        transcript_text="完成交付，下一步验收",
        source_type_key="人工录入",
        cutoff=utc_now() - timedelta(seconds=60),
    )


def test_duplicate_detection_uses_submitter_id_not_same_name(update_identity_db):
    db = update_identity_db
    db.add_all(
        [
            models.UpdateSubmission(id=1, project_id=1, submitter="汇报人甲", submitter_id=1, transcript_text="完成交付，下一步验收", source_type="人工录入"),
            models.UpdateSubmission(id=2, project_id=1, submitter="汇报人甲", submitter_id=2, transcript_text="完成交付，下一步验收", source_type="人工录入"),
        ]
    )
    db.commit()

    row = _find(db, {"person_id": 1, "name": "汇报人甲"})

    assert row is not None and row.id == 1


def test_duplicate_detection_rejects_ambiguous_username_name_collision(update_identity_db):
    db = update_identity_db
    db.add(
        models.UpdateSubmission(
            id=3,
            project_id=1,
            submitter="alice",
            submitter_id=None,
            transcript_text="完成交付，下一步验收",
            source_type="人工录入",
        )
    )
    db.commit()

    assert _find(db, {"person_id": 1, "name": "汇报人甲"}) is None
