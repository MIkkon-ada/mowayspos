from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
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


def test_subtask_detail_includes_execution_schedule_summary():
    source = Path(__file__).resolve().parents[1] / "app" / "routers" / "subtasks.py"
    assert 'result["execution_schedules"]' in source.read_text(encoding="utf-8")


def test_pending_close_project_rejects_execution_schedule_create_without_writing():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Owner", is_active=True),
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.Project(id=1, name="项目", status="pending_close", is_active=False),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
            models.Task(id=1, project_id=1, key_task="重点工作"),
            models.SubTask(id=1, task_id=1, title="关键任务", assignee="Owner"),
        ]
    )
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        execution_schedules.create_execution_schedule(
            1,
            schemas.ExecutionSchedulePayload(plan_type="week", title="不得写入"),
            current_user="owner",
            db=db,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "项目正在结束审核或已经结束，不允许执行该操作。"
    assert db.query(models.ExecutionSchedule).count() == 0


def test_execution_schedule_list_requires_project_access():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Owner", is_active=True),
            models.Person(id=2, name="Outsider", is_active=True),
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.Account(username="outsider", password_hash="x", person_id=2, status="active"),
            models.Project(id=1, name="受保护项目", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
            models.Task(id=1, project_id=1, key_task="重点工作"),
            models.SubTask(id=1, task_id=1, title="关键任务", assignee="Owner"),
            models.ExecutionSchedule(id=1, subtask_id=1, plan_type="week", title="敏感执行计划"),
        ]
    )
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        execution_schedules.list_execution_schedules(1, current_user="outsider", db=db)

    assert exc_info.value.status_code == 403
