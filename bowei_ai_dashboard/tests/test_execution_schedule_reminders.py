from datetime import date

from app import models
from app.database import Base
from app.services import execution_schedule_reminders as reminders
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_schedule(start_date: date, due_date: date, status: str = "待开始"):
    return models.ExecutionSchedule(
        subtask_id=1, plan_type="week", title="访谈", start_date=start_date,
        due_date=due_date, assignee="李娜", status=status,
    )


def test_reminder_kinds_cover_start_due_soon_and_overdue():
    today = date(2026, 8, 12)
    assert reminders.reminder_kinds_for(make_schedule(today, today + reminders.ONE_DAY), today) == {"start", "due_soon"}
    assert reminders.reminder_kinds_for(make_schedule(today - reminders.ONE_DAY, today - reminders.ONE_DAY), today) == {"overdue"}
    assert reminders.reminder_kinds_for(make_schedule(today, today, "已完成"), today) == set()


def test_reminder_notification_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([models.Project(id=1, name="项目", status="active", is_active=True), models.Task(id=1, project_id=1, key_task="工作", plan_time=""), models.SubTask(id=1, task_id=1, title="关键任务", assignee="李娜")])
    schedule = make_schedule(date(2026, 8, 12), date(2026, 8, 16)); schedule.id = 1
    db.add(schedule); db.commit()
    assert reminders.create_reminder_notification(db, schedule=schedule, recipient_id=1, kind="start", due_on=date(2026, 8, 12), project_id=1, link="/x") is True
    assert reminders.create_reminder_notification(db, schedule=schedule, recipient_id=1, kind="start", due_on=date(2026, 8, 12), project_id=1, link="/x") is False
