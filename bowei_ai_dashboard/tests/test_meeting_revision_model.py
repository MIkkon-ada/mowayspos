from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base


def test_meeting_revision_has_unique_meeting_version_and_complete_snapshot_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    meeting = models.Meeting(transcript_text="Original")
    db.add(meeting)
    db.flush()
    revision = models.MeetingRevision(
        meeting_id=meeting.id,
        version_no=1,
        saved_by="owner",
        transcript_text="Original",
        summary="Summary",
        task_list_json="[]",
        decision_items_json="[]",
        risk_items_json="[]",
    )
    db.add(revision)
    db.commit()

    assert revision.meeting_id == meeting.id
    assert revision.version_no == 1
    assert revision.transcript_text == "Original"
    assert revision.is_legacy_snapshot is False
