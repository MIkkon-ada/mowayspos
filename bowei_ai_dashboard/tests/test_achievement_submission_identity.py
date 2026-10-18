from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.achievement_submissions import _is_submission_submitter


@pytest.fixture
def achievement_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="同名提交人", is_active=True),
            models.Person(id=2, name="同名提交人", is_active=True),
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


def test_bound_achievement_submission_requires_matching_person_id(achievement_identity_db):
    row = models.AchievementSubmission(submitter="同名提交人", submitter_id=2)
    context = {"person_id": 1, "name": "同名提交人"}

    assert not _is_submission_submitter(context, row, "alice", achievement_identity_db)


def test_achievement_submission_legacy_username_resolves_through_account(achievement_identity_db):
    row = models.AchievementSubmission(submitter="alice", submitter_id=None)
    context = {"person_id": 1, "name": "同名提交人"}

    assert _is_submission_submitter(context, row, "alice", achievement_identity_db)


def test_ambiguous_legacy_display_name_does_not_authorize_withdrawal(achievement_identity_db):
    row = models.AchievementSubmission(submitter="同名提交人", submitter_id=None)
    context = {"person_id": 1, "name": "同名提交人"}

    assert not _is_submission_submitter(context, row, "alice", achievement_identity_db)


def test_unique_legacy_display_name_still_matches(achievement_identity_db):
    db = achievement_identity_db
    db.add(models.Person(id=3, name="唯一提交人", is_active=True))
    db.commit()
    row = models.AchievementSubmission(submitter="唯一提交人", submitter_id=None)
    context = {"person_id": 3, "name": "唯一提交人"}

    assert _is_submission_submitter(context, row, "carol", db)


def test_username_collision_with_another_person_name_is_not_guessed(achievement_identity_db):
    db = achievement_identity_db
    db.add(models.Person(id=3, name="alice", is_active=True))
    db.commit()
    row = models.AchievementSubmission(submitter="alice", submitter_id=None)
    context = {"person_id": 1, "name": "同名提交人"}

    assert not _is_submission_submitter(context, row, "alice", db)
