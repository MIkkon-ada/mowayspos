"""Full project lifecycle audit using every project role on an isolated database.

This is intentionally an end-to-end business-flow test rather than a unit test:
one project is taken from dispatch through owner submission, coach approval,
execution reporting, coordinator feedback, coach decision, owner confirmation,
and project close approval.  Each actor is also checked against an action that
must remain outside its scope.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.domain import submission_status as SS
from app.routers.confirmations import (
    ceo_decide,
    confirm,
    coordinator_feedback,
    escalate_ceo,
    pending,
    transfer_coordinator,
)
from app.routers.projects import (
    approve_project,
    approve_project_close_request,
    create_project_close_request,
    dispatch_project,
    owner_submit_project_profile,
)
from app.routers.updates import create_update


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db):
    people = {
        "admin": models.Person(id=1, name="技术管理员", system_role="super_admin", is_active=True),
        "company_ceo": models.Person(id=2, name="公司管理", system_role="company_ceo", is_active=True),
        "coach": models.Person(id=3, name="企业教练", system_role="normal_member", is_active=True),
        "owner": models.Person(id=4, name="项目负责人", system_role="normal_member", is_active=True),
        "coordinator": models.Person(id=5, name="项目统筹", system_role="normal_member", is_active=True),
        "member": models.Person(id=6, name="任务责任人", system_role="normal_member", is_active=True),
        "outsider": models.Person(id=7, name="项目外人员", system_role="normal_member", is_active=True),
    }
    db.add_all(people.values())
    db.add_all(
        models.Account(
            username=username,
            password_hash="x",
            person_id=person.id,
            status="active",
            is_tech_admin=username == "admin",
        )
        for username, person in people.items()
    )
    # 下发前的基础项目配置属于公司管理侧的立项准备阶段。
    project = models.Project(
        id=1,
        name="全流程审计项目",
        status="draft",
        is_active=False,
        objectives="验证项目目标",
        start_date="2026-09-01",
        end_date="2026-09-30",
        description="全流程角色审计",
    )
    db.add(project)
    db.flush()
    db.add_all(
        models.ProjectMember(
            project_id=project.id,
            person_id=people[key].id,
            person_name_snapshot=people[key].name,
            role=role,
        )
        for key, role in (
            ("coach", "project_ceo"),
            ("owner", "owner"),
            ("coordinator", "coordinator"),
            ("member", "member"),
        )
    )
    db.commit()
    return people, project


def _payload(member_id: int, *, title: str = "建立客户成功服务标准"):
    return schemas.ProjectProfilePayload(
        background="验证项目背景",
        objectives="验证项目目标",
        expected_outcomes="形成可复用成果",
        start_date="2026-09-01",
        end_date="2026-09-30",
        description="全流程角色审计",
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title=title,
                description="形成服务标准与 SOP",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="梳理现有服务流程",
                        evaluation_standard="形成流程图与问题清单",
                        assignee="任务责任人",
                        assignee_id=member_id,
                        helper="项目统筹",
                        helper_ids=[5],
                        plan_start="2026-09-01",
                        plan_end="2026-09-05",
                    )
                ],
            )
        ],
    )


def _report(project_id: int, subtask_id: int, submitter: str, title: str):
    return schemas.ExtractRequest(
        project_id=project_id,
        source_type="任务进展",
        title=title,
        transcript_text=f"{title}：完成关键任务并形成阶段成果",
        submitter=submitter,
        human_result={
            "task_reports": [
                {
                    "result_type": "subtask_progress",
                    "type": "progress",
                    "matched_subtask_id": subtask_id,
                    "completed": "完成关键任务并形成阶段成果",
                    "achievements": [{"name": title + "成果", "achievement_type": "技术成果"}],
                    "subtask_issues": [],
                }
            ],
        },
    )


def _close_payload():
    return schemas.ProjectCloseRequestCreatePayload(
        summary="项目目标已完成",
        objective_result="形成可复用成果",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="完成资料交接",
        retrospective="完成项目复盘",
    )


def _assert_forbidden(callable_, *args, **kwargs):
    with pytest.raises(HTTPException) as error:
        callable_(*args, **kwargs)
    assert error.value.status_code == 403


def test_full_role_lifecycle_runs_from_dispatch_to_close():
    db = _db()
    people, project = _seed(db)
    profile = _payload(people["member"].id)

    # 公司管理下发，只有负责人进入方案填写阶段。
    dispatched = dispatch_project(project.id, current_user="company_ceo", db=db)
    assert dispatched["status"] == "dispatched"
    _assert_forbidden(dispatch_project, project.id, current_user="owner", db=db)

    submitted = owner_submit_project_profile(project.id, profile, current_user="owner", db=db)
    assert submitted["submitted_for_review"] is True
    assert db.get(models.Project, project.id).status == "pending_review"
    _assert_forbidden(owner_submit_project_profile, project.id, profile, current_user="member", db=db)
    _assert_forbidden(owner_submit_project_profile, project.id, profile, current_user="coordinator", db=db)
    _assert_forbidden(owner_submit_project_profile, project.id, profile, current_user="outsider", db=db)

    # 企业教练审核通过，项目正式启动；公司管理不能代替项目企业教练审核。
    _assert_forbidden(approve_project, project.id, current_user="company_ceo", db=db)
    approved = approve_project(project.id, current_user="coach", db=db)
    assert approved["status"] == "active"
    assert db.get(models.Project, project.id).status == "active"

    task = db.query(models.Task).filter_by(project_id=project.id).one()
    subtask = db.query(models.SubTask).filter_by(task_id=task.id).one()

    # 任务责任人提交进展，提交阶段不能直接写入成果或问题。
    first = asyncio.run(
        create_update(
            _report(project.id, subtask.id, people["member"].name, "统筹反馈流"),
            current_user="member",
            db=db,
        )
    )
    first_id = first["submission"]["id"]
    assert db.get(models.UpdateSubmission, first_id).confirm_status == SS.S_NEW
    assert db.query(models.Achievement).filter_by(source_submission_id=first_id).count() == 0
    _assert_forbidden(confirm, first_id, schemas.ConfirmRequest(operator="member"), current_user="member", db=db)
    _assert_forbidden(confirm, first_id, schemas.ConfirmRequest(operator="coach"), current_user="coach", db=db)
    _assert_forbidden(confirm, first_id, schemas.ConfirmRequest(operator="coordinator"), current_user="coordinator", db=db)

    # 负责人转交统筹，统筹反馈后回到负责人确认。
    transfer_coordinator(
        first_id,
        schemas.WorkflowNoteRequest(note="请补充协调建议", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert db.get(models.UpdateSubmission, first_id).confirm_status == SS.S_WAITING_COORDINATOR
    _assert_forbidden(coordinator_feedback, first_id, schemas.WorkflowNoteRequest(note="越权"), current_user="member", db=db)
    coordinator_feedback(
        first_id,
        schemas.WorkflowNoteRequest(note="建议统一服务流程模板", operator="coordinator"),
        current_user="coordinator",
        db=db,
    )
    assert db.get(models.UpdateSubmission, first_id).confirm_status == SS.S_COORDINATOR_GIVEN
    confirm(first_id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
    assert db.get(models.UpdateSubmission, first_id).confirm_status == SS.S_CONFIRMED

    # 第二条提交走“负责人上报企业教练 → 企业教练批示 → 负责人确认”分支。
    second = asyncio.run(
        create_update(
            _report(project.id, subtask.id, people["member"].name, "企业教练决策流"),
            current_user="member",
            db=db,
        )
    )
    second_id = second["submission"]["id"]
    escalate_ceo(
        second_id,
        schemas.WorkflowNoteRequest(note="请确认重大方向", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert db.get(models.UpdateSubmission, second_id).confirm_status == SS.S_WAITING_CEO
    assert pending(tab="ceo", current_user="coach", db=db)
    assert pending(tab="ceo", current_user="owner", db=db) == []
    ceo_decide(
        second_id,
        schemas.WorkflowNoteRequest(note="方向确认，继续推进", operator="coach"),
        current_user="coach",
        db=db,
    )
    assert db.get(models.UpdateSubmission, second_id).confirm_status == SS.S_CEO_DECIDED
    confirm(second_id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
    assert db.get(models.UpdateSubmission, second_id).confirm_status == SS.S_CONFIRMED

    # 技术管理员保留全局兜底确认能力，但仍需走正常的提交状态机。
    third = asyncio.run(
        create_update(
            _report(project.id, subtask.id, people["member"].name, "技术管理员确认流"),
            current_user="member",
            db=db,
        )
    )
    third_id = third["submission"]["id"]
    confirm(third_id, schemas.ConfirmRequest(operator="admin"), current_user="admin", db=db)
    assert db.get(models.UpdateSubmission, third_id).confirm_status == SS.S_CONFIRMED

    # 项目负责人发起结束申请，企业教练批准，项目归档前的所有关键角色均已覆盖。
    _assert_forbidden(create_project_close_request, project.id, _close_payload(), current_user="member", db=db)
    close_request = create_project_close_request(project.id, _close_payload(), current_user="owner", db=db)
    assert close_request["status"] == "pending"
    assert db.get(models.Project, project.id).status == "pending_close"
    _assert_forbidden(approve_project_close_request, project.id, close_request["id"], schemas.ProjectCloseReviewPayload(review_comment="越权"), current_user="owner", db=db)
    closed = approve_project_close_request(
        project.id,
        close_request["id"],
        schemas.ProjectCloseReviewPayload(review_comment="审核通过"),
        current_user="coach",
        db=db,
    )
    assert closed["status"] == "approved"
    assert db.get(models.Project, project.id).status == "ended"
