from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base


def test_month_plan_persists_optional_dates_and_business_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = models.ExecutionSchedule(
        subtask_id=1,
        plan_type="month",
        plan_month="2026-08",
        title="完成本月方案",
        expected_output="确认可执行方案",
        assignee="邹奇敏",
        assignee_id=2,
        collaborator_ids=[3, 4],
        status="进行中",
        progress_note="已完成首版",
        risk_dependency="等待合作方确认",
    )
    db.add(row)
    db.commit()
    loaded = db.get(models.ExecutionSchedule, row.id)

    assert loaded.plan_month == "2026-08"
    assert loaded.start_date is None
    assert loaded.due_date is None
    assert loaded.expected_output == "确认可执行方案"
    assert loaded.collaborator_ids == [3, 4]
