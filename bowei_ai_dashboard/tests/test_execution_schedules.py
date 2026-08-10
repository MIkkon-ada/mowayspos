from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models
from app import schemas
from app.routers import execution_schedules
from app.database import Base


def test_execution_schedule_reminder_is_unique():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        models.Project(id=1, name="项目", status="active", is_active=True),
        models.Task(id=1, project_id=1, key_task="重点工作", plan_time=""),
        models.SubTask(id=1, task_id=1, title="关键任务", assignee="李娜"),
    ])
    db.commit()
    schedule = models.ExecutionSchedule(
        subtask_id=1, plan_type="week", title="访谈业务部门",
        start_date=date(2026, 8, 12), due_date=date(2026, 8, 16),
        assignee="李娜", created_by="PM",
    )
    db.add(schedule)
    db.commit()
    db.add_all([
        models.ExecutionScheduleReminder(schedule_id=schedule.id, reminder_kind="start", due_on=date(2026, 8, 12), recipient_id=1),
        models.ExecutionScheduleReminder(schedule_id=schedule.id, reminder_kind="start", due_on=date(2026, 8, 12), recipient_id=1),
    ])
    with pytest.raises(IntegrityError):
        db.commit()


def test_execution_schedule_payload_rejects_inverted_dates():
    with pytest.raises(ValueError, match="截止日期"):
        schemas.ExecutionSchedulePayload(
            plan_type="week", title="访谈", start_date=date(2026, 8, 16), due_date=date(2026, 8, 12)
        )


def test_schedule_projection_marks_overdue_and_due_soon():
    row = models.ExecutionSchedule(
        id=1, subtask_id=1, plan_type="month", title="初稿",
        start_date=date(2026, 8, 1), due_date=date(2026, 8, 11), assignee="李娜",
    )
    projected = execution_schedules.to_schedule_dict(row, today=date(2026, 8, 12))
    assert projected["is_overdue"] is True
    assert projected["is_due_soon"] is False
