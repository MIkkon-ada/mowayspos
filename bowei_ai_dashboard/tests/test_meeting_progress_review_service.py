import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.meeting_progress_review import (
    load_approved_baseline,
    normalize_review_candidates,
    parse_named_reports,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_load_approved_baseline_uses_final_snapshot():
    db = make_session()
    db.add(
        models.KickoffAgentRun(
            project_id=1,
            snapshot_json='{"tasks": [{"id": 1}]}',
            approved_snapshot_json='{"tasks": [{"id": 2}]}',
            result_json="{}",
            status="approved",
        )
    )
    db.commit()

    baseline = load_approved_baseline(1, db)

    assert baseline["tasks"][0]["id"] == 2


def test_parse_named_reports_rejects_unknown_names():
    reports = parse_named_reports("张三：完成接口设计\n陌生人：已完成", {"张三"})

    assert reports == [{"member_name": "张三", "report_text": "完成接口设计"}]


def test_normalize_review_requires_verbatim_evidence():
    normalized = normalize_review_candidates(
        [{"member_name": "张三", "status": "completed", "evidence_quote": ""}],
        "张三：本周继续推进",
        {"张三"},
    )

    assert normalized[0]["status"] == "not_mentioned"
    assert json.loads(normalized[0]["validation_json"])


def test_normalize_review_accepts_evidence_quote_from_transcript():
    normalized = normalize_review_candidates(
        [
            {
                "member_name": "张三",
                "status": "completed",
                "evidence_quote": "张三：已完成接口设计",
                "suggested_task_status": "已完成",
            }
        ],
        "张三：已完成接口设计",
        {"张三"},
    )

    assert normalized[0]["status"] == "completed"
    assert normalized[0]["validation_json"] == "[]"
