from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_workspace(db):
    project = models.Project(id=1, name="AI升级计划", status="active", is_active=True)
    other_project = models.Project(id=2, name="其他项目", status="active", is_active=True)
    owner = models.Person(id=1, name="负责人", is_active=True)
    helper = models.Person(id=2, name="协同人", is_active=True)
    outsider = models.Person(id=3, name="外部成员", is_active=True)
    db.add_all(
        [
            project,
            other_project,
            owner,
            helper,
            outsider,
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.ProjectMember(
                project_id=1,
                person_id=1,
                person_name_snapshot="负责人",
                role="owner",
            ),
            models.ProjectMember(
                project_id=1,
                person_id=2,
                person_name_snapshot="协同人",
                role="member",
            ),
            models.ProjectMember(
                project_id=2,
                person_id=3,
                person_name_snapshot="外部成员",
                role="member",
            ),
        ]
    )
    workstream = models.Task(id=10, project_id=1, key_task="形成项目执行体系")
    key_task = models.SubTask(
        id=20,
        task_id=10,
        title="完成系统模块梳理与迭代",
        assignee="负责人",
        assignee_id=1,
        collaborator_ids=[2],
        status="进行中",
    )
    db.add_all([workstream, key_task])
    db.commit()
    return project, workstream, key_task


def test_due_semantics_support_exact_fuzzy_and_unknown_without_fake_dates():
    exact = schemas.MonthPlanCreatePayload(
        title="精确计划",
        expected_output="交付物",
        assignee_id=1,
        start_date=date(2026, 7, 13),
        due_kind="exact",
        due_date=date(2026, 7, 28),
    )
    fuzzy = schemas.MonthPlanCreatePayload(
        title="模糊计划",
        expected_output="交付物",
        assignee_id=1,
        start_date=date(2026, 7, 13),
        due_kind="fuzzy",
        due_label="预计9月底",
        due_reference_date=date(2026, 9, 30),
    )
    unknown = schemas.MonthPlanCreatePayload(
        title="待定计划",
        expected_output="交付物",
        assignee_id=1,
        due_kind="unknown",
    )

    assert exact.due_date == date(2026, 7, 28)
    assert fuzzy.due_date is None
    assert fuzzy.due_label == "预计9月底"
    assert unknown.due_date is None
    assert unknown.due_label is None
    assert unknown.due_reference_date is None


def test_due_semantics_reject_fake_or_contradictory_storage():
    with pytest.raises(ValueError):
        schemas.MonthPlanCreatePayload(
            title="错误计划",
            expected_output="交付物",
            assignee_id=1,
            due_kind="unknown",
            due_label="暂未确定",
        )
    with pytest.raises(ValueError):
        schemas.MonthPlanCreatePayload(
            title="错误计划",
            expected_output="交付物",
            assignee_id=1,
            due_kind="fuzzy",
            due_label="预计9月底",
            due_date=date(2026, 9, 30),
        )


def test_current_progress_uses_effective_time_and_allows_same_status_progress():
    from app.services.key_task_execution import current_progress_dict, record_execution_event

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    now = datetime(2026, 7, 24, 14, 30)
    record_execution_event(
        db,
        project_id=1,
        key_task_id=key_task.id,
        event_type="work_submission",
        source_type="update_submission",
        source_id=100,
        dedupe_key="submission:100:key-task:20",
        actor_person_id=1,
        actor_name="负责人",
        occurred_at=now - timedelta(days=2),
        confirmed_at=now,
        effective_at=now,
        affects_current_progress=True,
        status_before="进行中",
        status_after="进行中",
        progress_summary="已完成模块清单初稿",
        next_step="组织方案评审",
    )
    record_execution_event(
        db,
        project_id=1,
        key_task_id=key_task.id,
        event_type="manual_progress_update",
        source_type="key_task",
        source_id=key_task.id,
        dedupe_key="manual:older-effective",
        actor_person_id=1,
        actor_name="负责人",
        occurred_at=now,
        confirmed_at=now + timedelta(hours=1),
        effective_at=now - timedelta(hours=1),
        affects_current_progress=True,
        progress_summary="更晚确认但更早生效的记录",
    )
    db.commit()

    current = current_progress_dict(db, key_task.id)

    assert current["progress_summary"] == "已完成模块清单初稿"
    assert current["next_step"] == "组织方案评审"
    assert current["effective_at"].startswith("2026-07-24T14:30")


def test_execution_event_deduplicates_the_same_source_action():
    from app.services.key_task_execution import record_execution_event

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    payload = dict(
        project_id=1,
        key_task_id=key_task.id,
        event_type="work_submission",
        source_type="update_submission",
        source_id=101,
        dedupe_key="submission:101:key-task:20",
        actor_name="负责人",
        occurred_at=datetime(2026, 7, 24, 10),
        confirmed_at=datetime(2026, 7, 24, 11),
        effective_at=datetime(2026, 7, 24, 11),
        affects_current_progress=True,
        progress_summary="完成一项工作",
    )

    first = record_execution_event(db, **payload)
    second = record_execution_event(db, **payload)
    db.commit()

    assert first.id == second.id
    assert db.query(models.KeyTaskExecutionEvent).count() == 1


def test_published_meeting_without_approval_does_not_create_progress():
    from app.services.key_task_execution import current_progress_dict, timeline_dicts

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    db.add(
        models.Meeting(
            id=30,
            project_id=1,
            title="项目周会",
            meeting_type="weekly",
            transcript_text="AI 候选：模块已完成",
            publish_status="published",
        )
    )
    db.commit()

    assert current_progress_dict(db, key_task.id) is None
    assert timeline_dicts(db, key_task.id) == []


def test_meeting_approval_writeback_creates_confirmed_execution_event():
    from app.routers import meetings

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    meeting = models.Meeting(
        id=30,
        project_id=1,
        title="项目周会",
        meeting_type="weekly",
        transcript_text="负责人：模块清单初稿已完成",
        publish_status="published",
    )
    db.add(meeting)
    db.add(
        models.KickoffAgentRun(
            id=40,
            project_id=1,
            status="approved",
            snapshot_json="{}",
            approved_snapshot_json="{}",
        )
    )
    review = models.MeetingProgressReview(
        id=50,
        project_id=1,
        meeting_id=30,
        baseline_run_id=40,
        baseline_subtask_id=key_task.id,
        member_name="负责人",
        baseline_snapshot_json="{}",
        report_text="模块清单初稿已完成",
        status="in_progress",
        evidence_quote="负责人：模块清单初稿已完成",
        suggested_task_status="进行中",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    meetings.confirm_progress_review(
        meeting.id,
        review.id,
        schemas.MeetingProgressReviewConfirm(
            status="in_progress",
            suggested_task_status="进行中",
            review_comment="确认回填",
        ),
        current_user="owner",
        db=db,
    )

    event = db.query(models.KeyTaskExecutionEvent).one()
    assert event.source_type == "meeting_progress_review"
    assert event.source_id == review.id
    assert event.authority == "confirmed"
    assert event.affects_current_progress is True


def test_completion_eligibility_never_treats_zero_over_zero_as_complete():
    from app.services.key_task_execution import completion_eligibility_dict

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)

    assert completion_eligibility_dict(db, key_task.id)["state"] == "no_execution_plan"


def test_all_effective_plans_are_only_eligible_until_owner_confirms():
    from app.routers import key_tasks
    from app.services.key_task_execution import completion_eligibility_dict

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    db.add_all(
        [
            models.ExecutionSchedule(
                subtask_id=key_task.id,
                plan_type="month",
                title="完成模块清单",
                assignee="负责人",
                assignee_id=1,
                status="已完成",
                actual_output="模块清单",
            ),
            models.ExecutionSchedule(
                subtask_id=key_task.id,
                plan_type="month",
                title="已取消范围",
                assignee="负责人",
                assignee_id=1,
                status="已取消",
            ),
            models.ExecutionSchedule(
                subtask_id=key_task.id,
                plan_type="month",
                title="归档历史计划",
                assignee="负责人",
                assignee_id=1,
                status="进行中",
                is_archived=True,
            ),
        ]
    )
    db.commit()

    eligibility = completion_eligibility_dict(db, key_task.id)
    assert eligibility["state"] == "eligible"
    assert db.get(models.SubTask, key_task.id).status == "进行中"

    key_tasks.confirm_key_task_completion(
        key_task.id,
        schemas.KeyTaskCompletionRequest(note="计划已经全部验收"),
        current_user="owner",
        db=db,
    )

    assert db.get(models.SubTask, key_task.id).status == "已完成"
    assert db.query(models.KeyTaskExecutionEvent).filter_by(event_type="key_task_status_changed").count() == 1


def test_completed_key_task_must_be_reopened_before_adding_plan():
    from app.routers import key_tasks, monthly_plans

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    key_task.status = "已完成"
    db.commit()
    payload = schemas.MonthPlanCreatePayload(
        title="追加范围",
        expected_output="追加交付物",
        assignee_id=1,
    )

    with pytest.raises(HTTPException) as exc:
        monthly_plans.create_monthly_plan(key_task.id, payload, current_user="owner", db=db)
    assert exc.value.status_code == 409

    key_tasks.reopen_key_task(
        key_task.id,
        schemas.KeyTaskReopenRequest(reason="新增范围"),
        current_user="owner",
        db=db,
    )
    created = monthly_plans.create_monthly_plan(
        key_task.id, payload, current_user="owner", db=db
    )
    assert created["title"] == "追加范围"


def test_key_task_collaborators_require_project_members_and_exclude_owner():
    from app.routers import subtasks

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)

    with pytest.raises(HTTPException) as owner_exc:
        subtasks.update_subtask(
            key_task.id,
            schemas.SubTaskPayload(
                title=key_task.title,
                assignee="负责人",
                collaborator_ids=[1],
            ),
            current_user="owner",
            db=db,
        )
    assert owner_exc.value.status_code == 422

    with pytest.raises(HTTPException) as outsider_exc:
        subtasks.update_subtask(
            key_task.id,
            schemas.SubTaskPayload(
                title=key_task.title,
                assignee="负责人",
                collaborator_ids=[3],
            ),
            current_user="owner",
            db=db,
        )
    assert outsider_exc.value.status_code == 422


def test_workspace_api_returns_one_contract_without_percentages():
    from app.routers import key_tasks

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)

    result = key_tasks.get_execution_workspace(
        key_task.id, current_user="owner", db=db
    )

    assert set(result) == {
        "key_task",
        "project",
        "workstream",
        "current_progress",
        "completion_eligibility",
        "plan_summary",
        "execution_plans",
        "achievements",
        "issues",
        "timeline",
        "permissions",
    }
    assert result["current_progress"] is None
    assert result["plan_summary"] == {
        "total": 0,
        "completed": 0,
        "in_progress": 0,
        "not_started": 0,
    }
    assert "percent" not in str(result).lower()


def test_workspace_uses_workstream_plan_time_when_key_task_time_is_blank():
    from app.routers import key_tasks

    db = _db()
    _project, workstream, key_task = _seed_workspace(db)
    workstream.plan_time = "7.3-7.10"
    key_task.plan_time = ""
    db.commit()

    result = key_tasks.get_execution_workspace(
        key_task.id, current_user="owner", db=db
    )

    assert result["key_task"]["plan_time"] == "7.3-7.10"


def test_workspace_uses_legacy_note_collaborator_when_structured_list_is_empty():
    from app.routers import key_tasks

    db = _db()
    _project, _workstream, key_task = _seed_workspace(db)
    key_task.collaborator_ids = []
    key_task.notes = "协同人：郭瑞彬\n完成系统模块梳理迭代"
    db.commit()

    result = key_tasks.get_execution_workspace(
        key_task.id, current_user="owner", db=db
    )

    assert result["key_task"]["collaborators"] == [{"id": None, "name": "郭瑞彬"}]


def test_authorized_manual_achievement_enters_timeline_without_becoming_progress():
    from app.routers import achievements
    from app.services.key_task_execution import current_progress_dict, timeline_dicts

    db = _db()
    _project, workstream, key_task = _seed_workspace(db)
    achievements.create_achievement(
        schemas.AchievementPayload(
            project_id=1,
            name="模块梳理清单 v1.0",
            achievement_type="文档",
            related_task_id=workstream.id,
            related_subtask_id=key_task.id,
            owner="负责人",
            status="已验收",
        ),
        current_user="owner",
        db=db,
    )

    timeline = timeline_dicts(db, key_task.id)
    assert [item["event_type"] for item in timeline] == ["achievement_created"]
    assert current_progress_dict(db, key_task.id) is None


def test_authorized_manual_issue_enters_timeline_without_becoming_progress():
    from app.routers import issues
    from app.services.key_task_execution import current_progress_dict, timeline_dicts

    db = _db()
    _project, workstream, key_task = _seed_workspace(db)
    issues.create_issue(
        schemas.IssuePayload(
            project_id=1,
            issue_type="风险",
            description="模块依赖关系仍待确认",
            related_task_id=workstream.id,
            related_subtask_id=key_task.id,
            owner="负责人",
            priority="高",
        ),
        current_user="owner",
        db=db,
    )

    timeline = timeline_dicts(db, key_task.id)
    assert [item["event_type"] for item in timeline] == ["issue_created"]
    assert current_progress_dict(db, key_task.id) is None


def test_manual_issue_update_adds_a_separate_append_only_timeline_event():
    from app.routers import issues
    from app.services.key_task_execution import timeline_dicts

    db = _db()
    _project, workstream, key_task = _seed_workspace(db)
    created = issues.create_issue(
        schemas.IssuePayload(
            project_id=1,
            description="模块依赖关系仍待确认",
            related_task_id=workstream.id,
            related_subtask_id=key_task.id,
            owner="负责人",
        ),
        current_user="owner",
        db=db,
    )
    issues.update_issue(
        created["id"],
        schemas.IssuePayload(
            project_id=1,
            description="模块依赖关系已进入确认流程",
            related_task_id=workstream.id,
            related_subtask_id=key_task.id,
            owner="负责人",
            status="处理中",
        ),
        current_user="owner",
        db=db,
    )

    assert [item["event_type"] for item in timeline_dicts(db, key_task.id)] == [
        "issue_updated",
        "issue_created",
    ]
