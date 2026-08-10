from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models
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
