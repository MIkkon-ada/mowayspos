from __future__ import annotations

import asyncio

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers import (
    achievement_submissions,
    achievements,
    confirmations,
    issues,
    meetings,
    projects,
    subtasks,
    tasks,
    updates,
)


FROZEN_MESSAGE = "项目正在结束审核或已经结束，不允许执行该操作。"


def _seed(status: str):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for pid, name, username in [
        (1, "Owner", "owner"),
        (2, "Coach", "coach"),
        (3, "Member", "member"),
        (4, "Target", "target"),
    ]:
        db.add(models.Person(id=pid, name=name, system_role="normal_member", is_active=True))
        db.add(models.Account(username=username, password_hash="x", person_id=pid, status="active"))
    project = models.Project(id=1, name="Project", status=status, is_active=False)
    db.add(project)
    db.add_all(
        [
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Coach", role="project_ceo"),
            models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Member", role="member"),
        ]
    )
    task = models.Task(project_id=1, special_project="Project", key_task="Workstream", owner="Owner")
    db.add(task)
    db.flush()
    submission = models.UpdateSubmission(
        project_id=1,
        transcript_text="Pending",
        confirm_status="待确认",
        human_result_json="{}",
    )
    db.add(submission)
    change = models.MemberChangeRequest(
        project_id=1,
        requester_person_id=1,
        action="add",
        target_person_id=4,
        target_person_name="Target",
        to_role="member",
        reason="Need help",
        status="pending",
    )
    db.add(change)
    db.commit()
    return db, task.id, submission.id, change.id


def _expect_frozen(callable_, *, exact_message: bool = True):
    with pytest.raises(HTTPException) as exc:
        callable_()
    assert exc.value.status_code == 409
    if exact_message:
        assert exc.value.detail == FROZEN_MESSAGE


@pytest.mark.parametrize("target", ["pending_close", "ended", "archived"])
@pytest.mark.parametrize("field", ["status", "lifecycle_status"])
def test_project_patch_cannot_enter_managed_close_or_archive_states(field: str, target: str):
    db, *_ = _seed("active")
    _expect_frozen(
        lambda: projects.update_project(
            1,
            schemas.ProjectPatchPayload(**{field: target}),
            current_user="moways",
            db=db,
        )
    )
    assert db.get(models.Project, 1).status == "active"


@pytest.mark.parametrize("status", ["pending_close", "ended"])
def test_project_patch_cannot_leave_close_frozen_states(status: str):
    db, *_ = _seed(status)
    _expect_frozen(
        lambda: projects.update_project(
            1,
            schemas.ProjectPatchPayload(status="active", description="bypass"),
            current_user="moways",
            db=db,
        )
    )
    assert db.get(models.Project, 1).status == status


@pytest.mark.parametrize("status", ["active", "pending_close"])
def test_archive_rejects_every_source_except_ended(status: str):
    db, *_ = _seed(status)
    with pytest.raises(HTTPException) as exc:
        projects.archive_project(1, current_user="moways", db=db)
    assert exc.value.status_code == 409
    assert db.get(models.Project, 1).status == status


def test_superadmin_archive_allows_only_ended_to_archived():
    db, *_ = _seed("ended")
    result = projects.archive_project(1, current_user="moways", db=db)
    assert result["status"] == "archived"
    assert db.get(models.Project, 1).status == "archived"


def _project_action(db, task_id: int, submission_id: int, change_id: int, action: str):
    member_id = db.query(models.ProjectMember).filter_by(project_id=1, person_id=3, role="member").one().id
    calls = {
        "project_patch": lambda: projects.update_project(
            1, schemas.ProjectPatchPayload(description="change"), current_user="moways", db=db
        ),
        "member_add": lambda: projects.add_member(
            1, schemas.ProjectMemberPayload(person_id=4, role="coordinator"), current_user="moways", db=db
        ),
        "member_patch": lambda: projects.update_member(
            1,
            member_id,
            schemas.ProjectMemberPatchPayload(note="change"),
            current_user="moways",
            db=db,
        ),
        "member_delete": lambda: projects.remove_member(1, member_id, current_user="moways", db=db),
        "member_change_create": lambda: projects.create_member_change_request(
            1,
            schemas.MemberChangeRequestPayload(target_person_id=4, to_role="coordinator", reason="Need"),
            current_user="owner",
            db=db,
        ),
        "member_change_approve": lambda: projects.approve_member_change_request(
            1, change_id, schemas.MemberChangeReviewPayload(), current_user="coach", db=db
        ),
        "member_change_reject": lambda: projects.reject_member_change_request(
            1, change_id, schemas.MemberChangeReviewPayload(), current_user="coach", db=db
        ),
        "dispatch": lambda: projects.dispatch_project(1, current_user="moways", db=db),
        "owner_submit": lambda: projects.owner_submit_project_profile(
            1, schemas.ProjectProfilePayload(), current_user="owner", db=db
        ),
        "return": lambda: projects.return_project(1, current_user="coach", db=db),
        "approve": lambda: projects.approve_project(1, current_user="coach", db=db),
        "kickoff": lambda: projects.kickoff_project(1, current_user="moways", db=db),
    }
    return calls[action]


@pytest.mark.parametrize("status", ["pending_close", "ended"])
@pytest.mark.parametrize(
    "action",
    [
        "project_patch",
        "member_add",
        "member_patch",
        "member_delete",
        "member_change_create",
        "member_change_approve",
        "member_change_reject",
        "dispatch",
        "owner_submit",
        "return",
        "approve",
        "kickoff",
    ],
)
def test_project_internal_writes_are_frozen(status: str, action: str):
    db, task_id, submission_id, change_id = _seed(status)
    before = {
        "project": db.get(models.Project, 1).status,
        "members": db.query(models.ProjectMember).count(),
        "changes": db.query(models.MemberChangeRequest).count(),
        "logs": db.query(models.OperationLog).count(),
    }
    _expect_frozen(_project_action(db, task_id, submission_id, change_id, action))
    after = {
        "project": db.get(models.Project, 1).status,
        "members": db.query(models.ProjectMember).count(),
        "changes": db.query(models.MemberChangeRequest).count(),
        "logs": db.query(models.OperationLog).count(),
    }
    assert after == before


def _business_action(db, task_id: int, submission_id: int, action: str):
    calls = {
        "task": lambda: tasks.create_task(
            schemas.TaskPayload(project_id=1, key_task="New workstream"), current_user="owner", db=db
        ),
        "subtask": lambda: subtasks.create_subtask(
            task_id,
            schemas.SubTaskPayload(title="New key task", assignee="Owner"),
            current_user="owner",
            db=db,
        ),
        "update": lambda: asyncio.run(
            updates.create_update(
                schemas.ExtractRequest(
                    project_id=1,
                    source_type="人工录入",
                    transcript_text="Status update",
                    human_result={},
                ),
                current_user="owner",
                db=db,
            )
        ),
        "confirmation": lambda: confirmations._require_submission_writable(
            db.get(models.UpdateSubmission, submission_id),
            {"is_tech_admin": True},
            db,
        ),
        "achievement": lambda: achievements.create_achievement(
            schemas.AchievementPayload(project_id=1, name="Asset"), current_user="owner", db=db
        ),
        "achievement_submission": lambda: achievement_submissions.create_submission(
            schemas.AchievementSubmissionPayload(project_id=1, related_task_id=task_id, name="Asset"),
            current_user="owner",
            db=db,
        ),
        "issue": lambda: issues.create_issue(
            schemas.IssuePayload(project_id=1, description="Issue"), current_user="owner", db=db
        ),
        "meeting": lambda: meetings.create_meeting(
            schemas.MeetingPayload(project_id=1, title="Meeting"), current_user="owner", db=db
        ),
    }
    return calls[action]


@pytest.mark.parametrize("status", ["pending_close", "ended"])
@pytest.mark.parametrize(
    "action",
    [
        "task",
        "subtask",
        "update",
        "confirmation",
        "achievement",
        "achievement_submission",
        "issue",
        "meeting",
    ],
)
def test_business_writes_are_frozen_without_side_effects(status: str, action: str):
    db, task_id, submission_id, _change_id = _seed(status)
    counts_before = {
        model: db.query(model).count()
        for model in (
            models.Task,
            models.SubTask,
            models.UpdateSubmission,
            models.Achievement,
            models.AchievementSubmission,
            models.Issue,
            models.Meeting,
            models.OperationLog,
        )
    }
    _expect_frozen(
        _business_action(db, task_id, submission_id, action),
        exact_message=action != "update",
    )
    counts_after = {model: db.query(model).count() for model in counts_before}
    assert counts_after == counts_before
