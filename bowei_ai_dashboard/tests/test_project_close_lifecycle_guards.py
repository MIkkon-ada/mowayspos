from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

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
from app.services.project_purge_storage import ProjectPurgeStorageError


FROZEN_MESSAGE = "项目正在结束审核或已经结束，不允许执行该操作。"
DELETE_PHRASE = "永久删除"


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


@pytest.mark.parametrize(
    "status",
    ["draft", "dispatched", "pending_kickoff", "pending_review", "returned", "active", "pending_close", "ended", "archived"],
)
def test_superadmin_can_permanently_delete_every_project_status_and_direct_records(status: str):
    db, task_id, submission_id, change_id = _seed(status)

    result = projects.delete_project(
        1,
        schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
        current_user="moways",
        db=db,
    )

    assert result == {"ok": True, "project_id": 1, "cleanup_pending": False, "cleanup_key": None}
    assert db.get(models.Project, 1) is None
    assert db.get(models.Task, task_id) is None
    assert db.get(models.UpdateSubmission, submission_id) is None
    assert db.get(models.MemberChangeRequest, change_id) is None
    assert db.query(models.ProjectMember).filter_by(project_id=1).count() == 0


def test_delete_requires_exact_project_name_and_destroy_phrase():
    db, *_ = _seed("draft")

    with pytest.raises(HTTPException) as exc:
        projects.delete_project(
            1,
            schemas.ProjectDeletePayload(confirm_name="Project ", confirm_phrase=DELETE_PHRASE),
            current_user="moways",
            db=db,
        )

    assert exc.value.status_code == 422
    assert db.get(models.Project, 1) is not None

    with pytest.raises(HTTPException) as exc:
        projects.delete_project(
            1,
            schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase="删除"),
            current_user="moways",
            db=db,
        )

    assert exc.value.status_code == 422
    assert db.get(models.Project, 1) is not None


def test_delete_requires_tech_admin():
    db, *_ = _seed("draft")

    with pytest.raises(HTTPException) as exc:
        projects.delete_project(
            1,
            schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 403
    assert db.get(models.Project, 1) is not None


def test_delete_rolls_back_when_dependency_cleanup_fails(monkeypatch):
    db, *_ = _seed("draft")

    def fail_after_cleanup(project, session):
        session.query(models.ProjectMember).filter_by(project_id=project.id).delete()
        raise RuntimeError("simulated cleanup failure")

    monkeypatch.setattr(projects, "_delete_project_data", fail_after_cleanup, raising=False)

    with pytest.raises(RuntimeError, match="simulated cleanup failure"):
        projects.delete_project(
            1,
            schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
            current_user="moways",
            db=db,
        )

    assert db.get(models.Project, 1) is not None
    assert db.query(models.ProjectMember).filter_by(project_id=1).count() == 3


def test_delete_purges_project_scoped_records_and_task_descendants():
    db, task_id, *_ = _seed("draft")
    task = db.get(models.Task, task_id)
    subtask = models.SubTask(task_id=task.id, title="Key task", assignee="Owner")
    achievement = models.Achievement(project_id=1, name="Asset")
    submission = models.AchievementSubmission(project_id=1, name="Asset submission")
    source = models.MeetingDocumentSource(
        project_id=1,
        original_name="meeting.docx",
        storage_key="purge-meeting-source",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=1,
        content_hash="a" * 64,
    )
    db.add_all([subtask, achievement, submission, source])
    db.flush()
    schedule = models.ExecutionSchedule(subtask_id=subtask.id, plan_type="week", title="Schedule")
    db.add(schedule)
    db.flush()
    subtask_id = subtask.id
    schedule_id = schedule.id
    db.add_all(
        [
            models.ExecutionScheduleReminder(
                schedule_id=schedule.id,
                reminder_kind="due",
                due_on=date(2026, 8, 27),
                recipient_id=1,
            ),
            models.AchievementAttachment(
                project_id=1,
                achievement_id=achievement.id,
                storage_key="purge-achievement-attachment",
                original_name="asset.txt",
                mime_type="text/plain",
                size_bytes=1,
            ),
            models.ProjectInitAttachment(
                project_id=1,
                storage_key="purge-init-attachment",
                original_name="init.txt",
                mime_type="text/plain",
                size_bytes=1,
                uploaded_by="moways",
            ),
            models.ProjectInitAnalysisRun(project_id=1, created_by="moways"),
            models.Issue(project_id=1, description="Issue"),
            models.ProjectCloseRequest(
                project_id=1,
                summary="Close summary",
                objective_result="Objective result",
                handover_plan="Handover plan",
                retrospective="Retrospective",
            ),
            models.ProjectMeetingRun(project_id=1, document_source_id=source.id),
            models.MeetingSkillRun(project_id=1, skill_name="summary", skill_version="1"),
            models.KickoffAgentRun(project_id=1),
            models.MeetingChangeSet(project_id=1),
            models.Notification(type="project_notice", title="Project notice", project_id=1),
        ]
    )
    db.commit()

    projects.delete_project(
        1,
        schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
        current_user="moways",
        db=db,
    )

    assert db.query(models.SubTask).filter_by(task_id=task_id).count() == 0
    assert db.query(models.ExecutionSchedule).filter_by(subtask_id=subtask_id).count() == 0
    assert db.query(models.ExecutionScheduleReminder).filter_by(schedule_id=schedule_id).count() == 0
    for model in (
        models.Achievement,
        models.AchievementSubmission,
        models.AchievementAttachment,
        models.ProjectInitAttachment,
        models.ProjectInitAnalysisRun,
        models.Issue,
        models.ProjectCloseRequest,
        models.MeetingDocumentSource,
        models.ProjectMeetingRun,
        models.MeetingSkillRun,
        models.KickoffAgentRun,
        models.MeetingChangeSet,
        models.Notification,
    ):
        assert db.query(model).filter_by(project_id=1).count() == 0


def _seed_project_purge_files(db, tmp_path: Path, monkeypatch):
    achievement_root = tmp_path / "achievement"
    init_root = tmp_path / "init"
    meeting_root = tmp_path / "meeting"
    monkeypatch.setenv("ACHIEVEMENT_ATTACHMENT_ROOT", str(achievement_root))
    monkeypatch.setenv("PROJECT_INIT_ATTACHMENT_ROOT", str(init_root))
    monkeypatch.setenv("PROJECT_MEETING_DOCUMENT_ROOT", str(meeting_root))
    db.add_all(
        [
            models.AchievementAttachment(
                project_id=1,
                storage_key="1/achievement.bin",
                original_name="achievement.bin",
                mime_type="application/octet-stream",
                size_bytes=1,
            ),
            models.ProjectInitAttachment(
                project_id=1,
                storage_key="1/init.bin",
                original_name="init.bin",
                mime_type="application/octet-stream",
                size_bytes=1,
                uploaded_by="moways",
            ),
            models.MeetingDocumentSource(
                project_id=1,
                storage_key="1/meeting.docx",
                original_name="meeting.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=1,
                content_hash="b" * 64,
            ),
        ]
    )
    db.commit()
    paths = [
        achievement_root / "1" / "achievement.bin",
        init_root / "1" / "init.bin",
        meeting_root / "1" / "meeting.docx",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return paths, [achievement_root, init_root, meeting_root]


def test_delete_physically_removes_project_attachment_payloads(tmp_path: Path, monkeypatch):
    db, *_ = _seed("active")
    paths, _roots = _seed_project_purge_files(db, tmp_path, monkeypatch)

    result = projects.delete_project(
        1,
        schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
        current_user="moways",
        db=db,
    )

    assert result["cleanup_pending"] is False
    assert db.get(models.Project, 1) is None
    assert all(not path.exists() for path in paths)


def test_delete_reports_pending_cleanup_and_allows_safe_retry(tmp_path: Path, monkeypatch):
    db, *_ = _seed("active")
    paths, roots = _seed_project_purge_files(db, tmp_path, monkeypatch)
    real_destroy = projects.destroy_staged_project_payloads

    def fail_destroy(_staged):
        raise ProjectPurgeStorageError("simulated cleanup failure")

    monkeypatch.setattr(projects, "destroy_staged_project_payloads", fail_destroy, raising=False)
    result = projects.delete_project(
        1,
        schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE),
        current_user="moways",
        db=db,
    )

    assert db.get(models.Project, 1) is None
    assert result["cleanup_pending"] is True
    assert result["cleanup_key"]
    assert all(not path.exists() for path in paths)

    monkeypatch.setattr(projects, "destroy_staged_project_payloads", real_destroy)
    retry = projects.retry_project_purge_cleanup(result["cleanup_key"], current_user="moways", db=db)
    assert retry == {"ok": True, "cleanup_key": result["cleanup_key"], "cleanup_pending": False}
    assert all(not (root / ".project-purge").exists() for root in roots)


def test_project_purge_deletes_task_references_before_subtasks():
    source = (Path(__file__).resolve().parents[1] / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    subtask_delete = source.index("db.query(models.SubTask).filter(models.SubTask.id.in_(subtask_ids)).delete")
    for reference_delete in (
        "db.query(models.UpdateSubmission).filter(models.UpdateSubmission.project_id == project_id).delete",
        "db.query(models.AchievementAttachment).filter(models.AchievementAttachment.project_id == project_id).delete",
        "db.query(models.AchievementSubmission).filter(models.AchievementSubmission.project_id == project_id).delete",
        "db.query(models.Achievement).filter(models.Achievement.project_id == project_id).delete",
        "db.query(models.Issue).filter(models.Issue.project_id == project_id).delete",
        "db.query(models.MeetingProgressReview).filter(models.MeetingProgressReview.project_id == project_id).delete",
    ):
        assert source.index(reference_delete) < subtask_delete


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
