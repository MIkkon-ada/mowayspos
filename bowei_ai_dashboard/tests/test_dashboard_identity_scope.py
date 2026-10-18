from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.permissions import get_user_context_from_db
from app.routers.achievement_submissions import list_submissions
from app.routers.dashboard import _project_overview
from app.routers.confirmations import my_rejected
from app.domain import submission_status as SS


@pytest.fixture
def dashboard_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="同名成员", system_role="normal_member", is_active=True),
            models.Person(id=2, name="同名成员", system_role="normal_member", is_active=True),
            models.Account(username="member_one", password_hash="x", person_id=1, status="active"),
            models.Account(username="member_two", password_hash="x", person_id=2, status="active"),
            models.Project(id=1, name="仪表盘身份项目", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="同名成员", role="member"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="同名成员", role="member"),
            models.Task(id=1, project_id=1, key_task="成员一重点工作", owner="同名成员", owner_id=1, special_project="仪表盘身份项目"),
            models.Task(id=2, project_id=1, key_task="成员二重点工作", owner="同名成员", owner_id=2, special_project="仪表盘身份项目"),
            models.UpdateSubmission(id=1, project_id=1, submitter="同名成员", submitter_id=1, transcript_text="成员一汇报"),
            models.UpdateSubmission(id=2, project_id=1, submitter="同名成员", submitter_id=2, transcript_text="成员二汇报"),
            models.AchievementSubmission(id=1, project_id=1, special_project="仪表盘身份项目", submitter="同名成员", submitter_id=1, name="成员一成果"),
            models.AchievementSubmission(id=2, project_id=1, special_project="仪表盘身份项目", submitter="同名成员", submitter_id=2, name="成员二成果"),
            models.Issue(id=1, project_id=1, description="成员一问题", owner="同名成员", owner_id=1, reporter="other"),
            models.Issue(id=2, project_id=1, description="成员二问题", owner="同名成员", owner_id=2, reporter="other"),
            models.Issue(id=3, project_id=1, description="身份文本冲突", owner="member_one", owner_id=2, reporter="other"),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_member_dashboard_scopes_tasks_submissions_and_issue_details_by_person_id(dashboard_identity_db):
    context = get_user_context_from_db("member_one", dashboard_identity_db)

    result = _project_overview(
        context,
        project_id=1,
        proj_name="仪表盘身份项目",
        owner_filter=None,
        status_filter=None,
        month_filter=None,
        db=dashboard_identity_db,
        current_user="member_one",
    )

    assert {row["id"] for row in result["recent"]["tasks"]} == {1}
    assert {row["id"] for row in result["role_queue"]["items"]} == {1}
    assert {row["id"] for row in result["recent"]["issues"]} == {1}


def test_achievement_submission_list_scopes_same_name_submitters_by_person_id(dashboard_identity_db):
    dashboard_identity_db.add(
        models.AchievementSubmission(
            id=3,
            project_id=1,
            special_project="仪表盘身份项目",
            submitter="member_one",
            submitter_id=None,
            name="成员一旧账号记录",
        )
    )
    dashboard_identity_db.commit()
    rows = list_submissions(
        project_id=1,
        current_user="member_one",
        db=dashboard_identity_db,
    )

    assert {row["id"] for row in rows} == {1, 3}


def test_rejected_submission_reminder_scopes_same_name_submitters_by_person_id(dashboard_identity_db):
    dashboard_identity_db.add_all(
        [
            models.UpdateSubmission(
                id=3, project_id=1, submitter="同名成员", submitter_id=1,
                confirm_status=SS.S_RETURNED, transcript_text="本人被退回",
            ),
            models.UpdateSubmission(
                id=4, project_id=1, submitter="同名成员", submitter_id=2,
                confirm_status=SS.S_RETURNED, transcript_text="他人被退回",
            ),
            models.UpdateSubmission(
                id=5, project_id=1, submitter="member_one", submitter_id=None,
                confirm_status=SS.S_RETURNED, transcript_text="本人旧账号记录",
            ),
        ]
    )
    dashboard_identity_db.commit()

    rows = my_rejected(current_user="member_one", db=dashboard_identity_db)

    assert {row["id"] for row in rows} == {3, 5}
