import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.domain import project_lifecycle as PL
from app.routers import projects


def _db(status: str = "draft"):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Company CEO", system_role="company_ceo", is_active=True),
            models.Person(id=2, name="Owner", system_role="normal_member", is_active=True),
            models.Person(id=3, name="Coach", system_role="normal_member", is_active=True),
            models.Account(username="company_ceo", password_hash="x", person_id=1, status="active"),
            models.Account(username="owner", password_hash="x", person_id=2, status="active"),
            models.Account(username="coach", password_hash="x", person_id=3, status="active"),
            models.Project(id=1, name="Project", status=status, is_active=status == "active"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Coach", role="project_ceo"),
        ]
    )
    db.commit()
    return db


def _set_dispatch_base_info(db):
    project = db.get(models.Project, 1)
    project.objectives = "\u9879\u76ee\u76ee\u6807"
    project.start_date = "2026-08-01"
    project.end_date = "2026-08-31"
    db.commit()


def test_approval_enters_active_without_pending_kickoff_gate():
    db = _db("pending_review")

    result = projects.approve_project(1, current_user="coach", db=db)

    assert result["status"] == "active"
    project = db.get(models.Project, 1)
    assert project.status == "active"
    assert project.is_active is True


def test_dispatch_changes_draft_to_dispatched_and_notifies_owner():
    db = _db("draft")
    _set_dispatch_base_info(db)

    result = projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert result["ok"] is True
    assert result["notified_to"] == 1
    assert result["status"] == "dispatched"
    project = db.get(models.Project, 1)
    assert project.status == "dispatched"
    assert project.is_active is False
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 1


def test_dispatch_allows_a_missing_end_date_and_notifies_owner():
    db = _db("draft")
    project = db.get(models.Project, 1)
    project.objectives = "项目目标"
    project.start_date = "2026-08-01"
    project.end_date = ""
    db.commit()

    result = projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert result == {"ok": True, "notified_to": 1, "status": "dispatched"}
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 1


def test_dispatch_notifies_only_strict_project_owners():
    db = _db("draft")
    db.add_all(
        [
            models.Person(id=4, name="Coordinator", system_role="normal_member", is_active=True),
            models.ProjectMember(project_id=1, person_id=4, person_name_snapshot="Coordinator", role="coordinator"),
        ]
    )
    db.commit()
    _set_dispatch_base_info(db)

    result = projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert result["notified_to"] == 1
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1, recipient_id=2).count() == 1
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1, recipient_id=4).count() == 0


def test_dispatch_locks_target_project_before_lifecycle_transition(monkeypatch):
    db = _db("draft")
    _set_dispatch_base_info(db)
    executed_statements = []
    execute = db.execute

    def record_execute(statement, *args, **kwargs):
        executed_statements.append(statement)
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", record_execute)

    projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert any(getattr(statement, "_for_update_arg", None) is not None for statement in executed_statements)


@pytest.mark.parametrize("status", ["pending_review", "dispatched"])
def test_dispatch_rejects_non_draft_lifecycle_without_changing_state_or_notifying_owner(status):
    db = _db(status)
    _set_dispatch_base_info(db)

    with pytest.raises(HTTPException, match="当前项目阶段不可下发"):
        projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert db.get(models.Project, 1).status == status
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 0


@pytest.mark.parametrize(
    ("start_date", "end_date", "message"),
    [
        ("2026-08-xx", "2026-08-31", "\u9879\u76ee\u5f00\u59cb\u65e5\u671f\u5fc5\u987b\u4f7f\u7528 YYYY-MM-DD \u683c\u5f0f\u3002"),
        ("2026-08-01", "2026-08-xx", "\u9879\u76ee\u7ed3\u675f\u65e5\u671f\u5fc5\u987b\u4f7f\u7528 YYYY-MM-DD \u683c\u5f0f\u3002"),
        ("2026-09-01", "2026-08-31", "项目结束日期不得早于开始日期。"),
    ],
)
def test_dispatch_requires_valid_chronological_iso_period(start_date, end_date, message):
    db = _db("draft")
    project = db.get(models.Project, 1)
    project.objectives = "项目目标"
    project.start_date = start_date
    project.end_date = end_date
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == message
    assert db.get(models.Project, 1).status == "draft"
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 0


@pytest.mark.parametrize(
    ("objectives", "start_date", "end_date"),
    [
        ("", "2026-08-01", "2026-08-31"),
        ("   ", "2026-08-01", "2026-08-31"),
        ("项目目标", "", "2026-08-31"),
    ],
)
def test_dispatch_requires_nonblank_objectives_and_start_date(objectives, start_date, end_date):
    db = _db("draft")
    project = db.get(models.Project, 1)
    project.objectives = objectives
    project.start_date = start_date
    project.end_date = end_date
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert exc_info.value.detail == "\u8bf7\u5148\u586b\u5199\u9879\u76ee\u76ee\u6807\u548c\u5f00\u59cb\u65e5\u671f\u540e\u518d\u4e0b\u53d1\u9879\u76ee\u3002"
    assert db.get(models.Project, 1).status == "draft"
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 0


def test_owner_cannot_submit_plan_while_project_is_still_draft():
    db = _db("draft")

    with pytest.raises(HTTPException, match="当前项目阶段不可提交立项信息"):
        projects.owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(),
            current_user="owner",
            db=db,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (schemas.ProjectProfilePayload(), "请至少新增一条重点工作"),
        (
            schemas.ProjectProfilePayload(
                work_progress_draft=[
                    schemas.ProjectWorkProgressTaskDraft(title="重点工作", subtasks=[]),
                ]
            ),
            "请至少添加一个关键任务",
        ),
        (
            schemas.ProjectProfilePayload(
                work_progress_draft=[
                    schemas.ProjectWorkProgressTaskDraft(
                        title="重点工作",
                        subtasks=[schemas.ProjectWorkProgressSubTaskDraft(title="关键任务")],
                    ),
                ]
            ),
            "请选择关键任务负责人",
        ),
    ],
)
def test_owner_submission_rejects_invalid_work_plan_without_lifecycle_mutation(payload, message):
    db = _db("dispatched")
    _set_dispatch_base_info(db)

    with pytest.raises(HTTPException) as exc_info:
        projects.owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == message
    assert db.get(models.Project, 1).status == "dispatched"


def test_owner_submission_preserves_dispatched_management_base_info_when_payload_attempts_overwrite():
    db = _db("dispatched")
    _set_dispatch_base_info(db)
    dispatched_project = db.get(models.Project, 1)
    dispatched_project.project_type = "管理层项目类型"
    dispatched_project.client_name = "管理层客户"
    dispatched_project.background = "管理层项目背景"
    dispatched_project.expected_outcomes = "管理层补充说明"
    dispatched_project.description = "管理层项目描述"
    db.commit()

    result = projects.owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            project_type="负责人尝试覆盖的项目类型",
            client_name="负责人尝试覆盖的客户",
            background="负责人尝试覆盖的项目背景",
            objectives="负责人尝试覆盖的目标",
            expected_outcomes="负责人尝试覆盖的补充说明",
            start_date="2026-09-01",
            end_date="2026-09-30",
            description="负责人尝试覆盖的项目描述",
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="有效重点工作",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(title="有效关键任务", assignee_id=2),
                    ],
                ),
            ],
        ),
        current_user="owner",
        db=db,
    )

    project = db.get(models.Project, 1)
    assert result["submitted_for_review"] is True
    assert project.status == "pending_review"
    assert project.project_type == "管理层项目类型"
    assert project.client_name == "管理层客户"
    assert project.background == "管理层项目背景"
    assert project.objectives == "项目目标"
    assert project.expected_outcomes == "管理层补充说明"
    assert project.start_date == "2026-08-01"
    assert project.end_date == "2026-08-31"
    assert project.description == "管理层项目描述"


def test_legacy_lifecycle_states_are_classified_for_compatibility():
    assert PL.is_execution_available("active") is True
    assert PL.is_execution_available("pending_kickoff") is True
    assert PL.is_owner_plan_editable("draft") is False
    assert PL.is_owner_plan_editable("dispatched") is True
    assert PL.is_owner_plan_editable("returned") is True
