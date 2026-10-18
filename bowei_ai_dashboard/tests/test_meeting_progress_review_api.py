import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import meetings


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(with_baseline: bool = True):
    db = _db()
    project = models.Project(id=1, name="Project", status="active", is_active=True)
    person = models.Person(id=1, name="Owner", is_active=True)
    account = models.Account(username="owner", password_hash="x", person_id=1, status="active")
    member = models.ProjectMember(
        project_id=1,
        person_id=1,
        person_name_snapshot="Owner",
        role="owner",
    )
    task = models.Task(id=10, project_id=1, key_task="接口工作")
    subtask = models.SubTask(id=20, task_id=10, title="接口设计", assignee="Owner")
    meeting = models.Meeting(
        id=30,
        project_id=1,
        title="周会",
        meeting_type="weekly",
        transcript_text="Owner：已完成接口设计",
        publish_status="draft",
    )
    db.add_all([project, person, account, member, task, subtask, meeting])
    db.flush()
    if with_baseline:
        db.add(
            models.KickoffAgentRun(
                id=40,
                project_id=1,
                status="approved",
                snapshot_json="{}",
                approved_snapshot_json=json.dumps(
                    {
                        "project_id": 1,
                        "tasks": [
                            {
                                "id": 10,
                                "title": "接口工作",
                                "subtasks": [
                                    {"id": 20, "title": "接口设计", "assignee": "Owner"}
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
        )
    db.commit()
    return db, meeting, subtask


def _analysis_snapshot(meeting, task=None, subtask=None):
    digest = hashlib.sha256((meeting.transcript_text or "").encode("utf-8")).hexdigest()
    target = None
    if task is not None and subtask is not None:
        target = {
            "task": {
                "id": task.id,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "status": task.status or "",
                "is_deleted": bool(task.is_deleted),
            },
            "subtask": {
                "id": subtask.id,
                "task_id": subtask.task_id,
                "updated_at": subtask.updated_at.isoformat() if subtask.updated_at else None,
                "status": subtask.status or "",
                "is_deleted": bool(subtask.is_deleted),
            },
        }
    return json.dumps({
        "task": {},
        "subtask": {},
        "analysis_transcript_sha256": digest,
        "target_at_analysis": target,
    })


def test_analyze_requires_approved_baseline():
    db, meeting, _subtask = _seed(with_baseline=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(meetings.analyze_progress_review(meeting.id, current_user="owner", db=db))

    assert exc.value.status_code == 409


def test_analyze_persists_pending_evidence_bound_rows(monkeypatch):
    db, meeting, _subtask = _seed()
    monkeypatch.setattr(
        meetings,
        "_do_analyze",
            lambda *_args, **_kwargs: {
            "reviews": [
                {
                    "member_name": "Owner",
                    "baseline_subtask_id": 20,
                    "status": "completed",
                    "report_text": "已完成接口设计",
                    "evidence_quote": "Owner：已完成接口设计",
                    "suggested_task_status": "已完成",
                    "reason": "原文明确说明完成",
                }
            ]
        },
    )

    result = asyncio.run(meetings.analyze_progress_review(meeting.id, current_user="owner", db=db))

    assert result["analysis_version"] == 1
    assert result["reviews"][0]["review_status"] == "pending"
    assert result["reviews"][0]["evidence_quote"] == "Owner：已完成接口设计"
    snapshot = json.loads(result["reviews"][0]["baseline_snapshot_json"])
    assert snapshot["analysis_transcript_sha256"] == hashlib.sha256(meeting.transcript_text.encode("utf-8")).hexdigest()


def test_analyze_rejects_stale_transcript_without_superseding_current_review(monkeypatch):
    db, meeting, subtask = _seed()
    existing = models.MeetingProgressReview(
        project_id=1,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已有待审核结果",
        status="in_progress",
        evidence_quote="已有证据",
        suggested_task_status="进行中",
        review_status="pending",
        analysis_version=1,
    )
    db.add(existing)
    db.commit()

    def change_transcript_during_analysis(session, *_args, **_kwargs):
        current_meeting = session.get(models.Meeting, meeting.id)
        current_meeting.transcript_text = "Owner：原文已在分析期间修改"
        session.commit()
        return {
            "reviews": [
                {
                    "member_name": "Owner",
                    "baseline_subtask_id": subtask.id,
                    "status": "completed",
                    "report_text": "已完成接口设计",
                    "evidence_quote": "已完成接口设计",
                    "suggested_task_status": "已完成",
                    "reason": "原文明确说明完成",
                }
            ]
        }

    monkeypatch.setattr(meetings, "_do_analyze", change_transcript_during_analysis)

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(meetings.asyncio, "to_thread", run_inline)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(meetings.analyze_progress_review(meeting.id, current_user="owner", db=db))

    assert exc.value.status_code == 409
    db.refresh(existing)
    assert existing.review_status == "pending"
    assert (
        db.query(models.MeetingProgressReview)
        .filter(models.MeetingProgressReview.meeting_id == meeting.id)
        .count()
        == 1
    )


def test_confirm_review_updates_subtask_and_marks_accepted():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=1,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    result = meetings.confirm_progress_review(
        meeting.id,
        review.id,
        SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
        current_user="owner",
        db=db,
    )

    assert result["review_status"] == "accepted"
    assert db.get(models.SubTask, subtask.id).status == "已完成"


def test_confirm_requires_analysis_source_snapshot_for_legacy_pending_review():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=meeting.project_id,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json="{}",
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 409
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
    assert db.get(models.SubTask, subtask.id).status != "已完成"


def test_confirm_failure_does_not_mark_review_accepted():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=1,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=999999,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    with pytest.raises(HTTPException):
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"


def test_confirm_rejects_stale_session_after_another_session_already_confirmed():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=1,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    stale_db = sessionmaker(bind=db.get_bind())()
    stale_review = stale_db.get(models.MeetingProgressReview, review.id)
    assert stale_review.review_status == "pending"

    first_result = meetings.confirm_progress_review(
        meeting.id,
        review.id,
        SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment="first"),
        current_user="owner",
        db=db,
    )
    assert first_result["review_status"] == "accepted"

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment="stale retry"),
            current_user="owner",
            db=stale_db,
        )

    assert exc.value.status_code == 409
    assert stale_db.get(models.MeetingProgressReview, review.id).review_status == "accepted"
    assert (
        db.query(models.KeyTaskExecutionEvent)
        .filter_by(dedupe_key=f"meeting_progress_review:{review.id}:confirmed")
        .count()
        == 1
    )


def test_confirm_rejects_transcript_edited_after_analysis_without_writeback():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=meeting.project_id,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()
    meeting.transcript_text = "Owner：接口设计仍在进行"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 409
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
    assert db.get(models.SubTask, subtask.id).status != "已完成"
    assert db.query(models.KeyTaskExecutionEvent).count() == 0


def test_confirm_rejects_task_changed_after_analysis_without_overwriting_it():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=meeting.project_id,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_task_id=subtask.task_id,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()
    subtask.status = "已完成"
    subtask.notes = "负责人已在其他入口更新"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="in_progress", suggested_task_status="进行中", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 409
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
    assert db.get(models.SubTask, subtask.id).status == "已完成"
    assert db.get(models.SubTask, subtask.id).notes == "负责人已在其他入口更新"


def test_confirm_rejects_archived_project_without_writing_progress_or_review():
    db, meeting, subtask = _seed()
    project = db.get(models.Project, meeting.project_id)
    project.status = "archived"
    project.is_active = False
    review = models.MeetingProgressReview(
        project_id=meeting.project_id,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 403
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
    assert db.get(models.SubTask, subtask.id).status != "已完成"
    assert (
        db.query(models.KeyTaskExecutionEvent)
        .filter_by(dedupe_key=f"meeting_progress_review:{review.id}:confirmed")
        .count()
        == 0
    )


def test_confirm_rejects_soft_deleted_task_target_without_writeback():
    db, meeting, subtask = _seed()
    subtask.is_deleted = True
    review = models.MeetingProgressReview(
        project_id=meeting.project_id,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=subtask.id,
        member_name="Owner",
        baseline_snapshot_json=_analysis_snapshot(meeting, db.get(models.Task, subtask.task_id), subtask),
        report_text="已完成接口设计",
        status="completed",
        evidence_quote="Owner：已完成接口设计",
        suggested_task_status="已完成",
        review_status="pending",
    )
    db.add(review)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 409
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
    assert db.get(models.SubTask, subtask.id).status != "已完成"
    assert (
        db.query(models.KeyTaskExecutionEvent)
        .filter_by(dedupe_key=f"meeting_progress_review:{review.id}:confirmed")
        .count()
        == 0
    )
