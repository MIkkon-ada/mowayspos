from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
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


def test_month_plan_payload_requires_valid_month_and_completed_output():
    with pytest.raises(ValueError, match="String should match pattern"):
        schemas.MonthPlanCreatePayload(
            plan_month="2026-13",
            title="完成方案",
            expected_output="方案定稿",
            assignee_id=2,
        )


def test_month_plan_payload_allows_no_month_group():
    payload = schemas.MonthPlanCreatePayload(
        plan_month=None,
        title="不按月份推进权限梳理",
        expected_output="权限清单",
        assignee_id=2,
    )

    assert payload.plan_month is None


def test_month_plan_rows_include_ungrouped_records():
    from app.routers import monthly_plans

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        models.ExecutionSchedule(
            subtask_id=1,
            plan_type="month",
            plan_month=None,
            title="未分月",
            expected_output="x",
            assignee="A",
            status="未开始",
        ),
        models.ExecutionSchedule(
            subtask_id=1,
            plan_type="month",
            plan_month="2026-08",
            title="八月",
            expected_output="x",
            assignee="A",
            status="未开始",
        ),
    ])
    db.commit()

    assert {row.title for row in monthly_plans._month_plan_rows(1, db)} == {"未分月", "八月"}

    with pytest.raises(ValueError, match="实际产出"):
        schemas.MonthPlanCreatePayload(
            plan_month="2026-08",
            title="完成方案",
            expected_output="方案定稿",
            assignee_id=2,
            status="已完成",
        )


def test_month_plan_projection_marks_overdue_and_sorts_by_management_order():
    from app.routers import monthly_plans

    rows = [
        models.ExecutionSchedule(id=1, subtask_id=1, plan_type="month", plan_month="2026-08", title="完成", expected_output="x", assignee="A", status="已完成"),
        models.ExecutionSchedule(id=2, subtask_id=1, plan_type="month", plan_month="2026-08", title="暂缓", expected_output="x", assignee="A", status="暂缓"),
        models.ExecutionSchedule(id=3, subtask_id=1, plan_type="month", plan_month="2026-08", title="逾期", expected_output="x", assignee="A", status="进行中", start_date=date(2026, 8, 1), due_date=date(2026, 8, 10)),
        models.ExecutionSchedule(id=4, subtask_id=1, plan_type="month", plan_month="2026-08", title="进行中", expected_output="x", assignee="A", status="进行中"),
        models.ExecutionSchedule(id=5, subtask_id=1, plan_type="month", plan_month="2026-08", title="未开始", expected_output="x", assignee="A", status="未开始"),
    ]

    result = monthly_plans.sort_month_plans(rows, today=date(2026, 8, 12))

    assert [row.id for row in result] == [3, 4, 2, 5, 1]
    assert monthly_plans.to_month_plan_dict(result[0], today=date(2026, 8, 12))["display_status"] == "已延期"


def test_month_plan_create_returns_business_fields_without_audit_fields():
    from app.routers import monthly_plans

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        models.Project(id=1, name="AI项目", status="active", is_active=True),
        models.Person(id=1, name="项目负责人"),
        models.Person(id=2, name="执行负责人"),
        models.Account(username="project-owner", password_hash="test", person_id=1, status="active"),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="项目负责人", role="owner"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="执行负责人", role="member"),
        models.Task(id=1, project_id=1, key_task="重点工作"),
        models.SubTask(id=1, task_id=1, title="关键任务", assignee="项目负责人"),
    ])
    db.commit()

    result = monthly_plans.create_monthly_plan(
        1,
        schemas.MonthPlanCreatePayload(
            plan_month="2026-08",
            title="完成联合市场活动方案",
            expected_output="可评审的活动方案",
            assignee_id=2,
            status="进行中",
        ),
        current_user="project-owner",
        db=db,
    )

    assert result["assignee"] == "执行负责人"
    assert result["expected_output"] == "可评审的活动方案"
    assert "created_by" not in result
    assert "updated_by" not in result
