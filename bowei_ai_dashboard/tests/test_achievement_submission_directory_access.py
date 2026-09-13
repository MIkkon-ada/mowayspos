import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import achievement_submissions


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="成员", is_active=True),
            models.Account(username="member", password_hash="x", person_id=1, status="active"),
            models.AchievementSubmission(id=1, name="历史未署名成果", submitter=""),
            models.AchievementSubmission(id=2, name="成员成果", submitter="成员"),
        ]
    )
    db.commit()
    return db


def test_achievement_submission_list_requires_an_authenticated_account():
    with pytest.raises(HTTPException) as exc_info:
        achievement_submissions.list_submissions(current_user="", db=_db())

    assert exc_info.value.status_code == 401


def test_authenticated_user_only_receives_their_achievement_submissions():
    rows = achievement_submissions.list_submissions(current_user="member", db=_db())

    assert [row["id"] for row in rows] == [2]
