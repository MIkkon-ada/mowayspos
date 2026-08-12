from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import meetings
from app.services.meeting_revisions import append_meeting_revision


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_revision_history_returns_newest_first_and_full_snapshots(monkeypatch):
    db = _db()
    meeting = models.Meeting(
        project_id=None,
        title="History",
        transcript_text="Original transcript",
        summary="V1",
        publish_status="published",
    )
    db.add(meeting)
    db.commit()
    append_meeting_revision(db, meeting, saved_by="owner")
    append_meeting_revision(db, meeting, {"summary": "V2"}, saved_by="reviewer")
    db.commit()
    monkeypatch.setattr(meetings, "require_login", lambda _user, _db: _user)
    monkeypatch.setattr(meetings, "get_user_context_from_db", lambda _user, _db: {"is_tech_admin": True, "is_ceo": False})

    rows = meetings.list_meeting_revisions(meeting.id, current_user="owner", db=db)

    assert [row["version_no"] for row in rows] == [2, 1]
    assert rows[0]["summary"] == "V2"
    assert rows[0]["transcript_text"] == "Original transcript"
    assert rows[0]["saved_by"] == "reviewer"


def test_revision_history_has_no_delete_or_mutation_operation():
    assert not hasattr(meetings, "delete_meeting_revision")
    assert not hasattr(meetings, "update_meeting_revision")
