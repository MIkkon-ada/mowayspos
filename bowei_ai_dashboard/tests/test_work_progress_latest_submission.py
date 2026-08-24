from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_subtask_risk_fields_are_persisted():
    assert {"risk_note", "risk_marked_by", "risk_marked_at"}.issubset(
        models.SubTask.__table__.c.keys()
    )

    db = _db()
    row = models.SubTask(task_id=1, title="关键任务", assignee="负责人")
    row.risk_note = "外部依赖尚未确认"
    row.risk_marked_by = "负责人"
    row.risk_marked_at = datetime(2026, 8, 24, 9, 0)
    db.add(row)
    db.commit()
    row_id = row.id
    db.expunge_all()
    row = db.get(models.SubTask, row_id)

    assert row.risk_note == "外部依赖尚未确认"
    assert row.risk_marked_by == "负责人"
    assert row.risk_marked_at == datetime(2026, 8, 24, 9, 0)
