from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_progress_review_snapshot_and_review_fields_round_trip():
    db = make_session()
    row = models.MeetingProgressReview(
        project_id=1,
        meeting_id=2,
        baseline_run_id=3,
        member_name="张三",
        baseline_snapshot_json='{"subtask_id": 7}',
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="张三：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(row)
    db.commit()

    loaded = db.get(models.MeetingProgressReview, row.id)
    assert loaded.evidence_quote == "张三：已完成接口设计"
    assert loaded.review_status == "pending"


def test_kickoff_run_has_approved_snapshot_json():
    assert hasattr(models.KickoffAgentRun, "approved_snapshot_json")
