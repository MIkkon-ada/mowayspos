from app import models, schemas
from app.services.meeting_revisions import append_meeting_revision
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base


def test_meeting_payload_and_model_keep_standard_header_fields_separate():
    payload = schemas.MeetingPayload(
        project_id=1,
        location="A 栋 301",
        organizer="吴肖",
        copied_to="项目负责人、相关成员",
    )
    row = models.Meeting(
        project_id=payload.project_id,
        location=payload.location,
        organizer=payload.organizer,
        copied_to=payload.copied_to,
    )

    assert row.location == "A 栋 301"
    assert row.organizer == "吴肖"
    assert row.copied_to == "项目负责人、相关成员"


def test_meeting_snapshot_keeps_standard_minutes_sections():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    meeting = models.Meeting(
        project_id=1,
        agenda_items_json='["市场推广"]',
        prior_action_items_json='[{"编号":"上周-01","状态":"已完成"}]',
        source_mode="standard_minutes",
        organizer="吴肖",
    )
    db.add(meeting)
    db.flush()

    revision = append_meeting_revision(db, meeting, saved_by="owner")

    assert revision.agenda_items_json == '["市场推广"]'
    assert revision.prior_action_items_json == '[{"编号":"上周-01","状态":"已完成"}]'
    assert revision.source_mode == "standard_minutes"
    assert revision.organizer == "吴肖"
