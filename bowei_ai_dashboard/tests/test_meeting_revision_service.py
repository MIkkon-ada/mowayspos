import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.meeting_revisions import append_meeting_revision


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _meeting(**overrides):
    values = {
        "project_id": 1,
        "title": "Weekly sync",
        "meeting_date": "2026-08-03",
        "host": "Owner",
        "transcript_text": "Owner: finish the report by Friday.",
        "summary": "Initial summary",
        "task_list_json": json.dumps([{"member": "Owner", "task": "Finish report", "deadline": "Friday"}]),
        "decision_items_json": "[]",
        "risk_items_json": "[]",
        "publish_status": "draft",
    }
    values.update(overrides)
    return models.Meeting(**values)


def test_first_save_creates_v1_without_losing_original_transcript():
    db = _db()
    meeting = _meeting()
    db.add(meeting)
    db.commit()

    revision = append_meeting_revision(db, meeting, {"summary": "Reviewed summary"}, saved_by="owner")
    db.commit()

    assert revision.version_no == 1
    assert revision.is_legacy_snapshot is False
    assert revision.transcript_text == "Owner: finish the report by Friday."
    assert meeting.transcript_text == "Owner: finish the report by Friday."
    assert meeting.summary == "Reviewed summary"


def test_each_save_appends_a_revision_and_keeps_previous_snapshot_unchanged():
    db = _db()
    meeting = _meeting()
    db.add(meeting)
    db.commit()

    first = append_meeting_revision(db, meeting, {"summary": "V1 summary"}, saved_by="owner")
    db.commit()
    second = append_meeting_revision(db, meeting, {"summary": "V2 summary"}, saved_by="owner")
    db.commit()

    assert (first.version_no, second.version_no) == (1, 2)
    assert db.get(models.MeetingRevision, first.id).summary == "V1 summary"
    assert db.get(models.MeetingRevision, second.id).summary == "V2 summary"


def test_first_edit_of_legacy_meeting_keeps_upgrade_snapshot_before_v1():
    db = _db()
    meeting = _meeting(summary="Legacy summary")
    db.add(meeting)
    db.commit()

    revision = append_meeting_revision(
        db,
        meeting,
        {"summary": "New V1 summary"},
        saved_by="owner",
        preserve_legacy=True,
    )
    db.commit()

    history = db.query(models.MeetingRevision).order_by(models.MeetingRevision.id.asc()).all()
    assert revision.version_no == 1
    assert len(history) == 2
    assert history[0].is_legacy_snapshot is True
    assert history[0].summary == "Legacy summary"
    assert history[1].is_legacy_snapshot is False
    assert history[1].summary == "New V1 summary"


def test_revision_save_removes_model_invented_year_from_action_deadline():
    db = _db()
    meeting = _meeting(
        transcript_text="Owner 8月3日前完成流程定稿。",
        task_list_json=json.dumps([{"member": "Owner", "task": "8月3日前完成流程定稿", "deadline": "2024-08-03"}], ensure_ascii=False),
    )
    db.add(meeting)
    db.commit()

    revision = append_meeting_revision(db, meeting, saved_by="owner")
    db.commit()

    assert json.loads(revision.task_list_json)[0]["deadline"] == "8月3日前"
