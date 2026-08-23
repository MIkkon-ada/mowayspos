import asyncio
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


def test_confirm_review_updates_subtask_and_marks_accepted():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=1,
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

    result = meetings.confirm_progress_review(
        meeting.id,
        review.id,
        SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
        current_user="owner",
        db=db,
    )

    assert result["review_status"] == "accepted"
    assert db.get(models.SubTask, subtask.id).status == "已完成"


def test_confirm_failure_does_not_mark_review_accepted():
    db, meeting, subtask = _seed()
    review = models.MeetingProgressReview(
        project_id=1,
        meeting_id=meeting.id,
        baseline_run_id=40,
        baseline_subtask_id=999999,
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

    with pytest.raises(HTTPException):
        meetings.confirm_progress_review(
            meeting.id,
            review.id,
            SimpleNamespace(status="completed", suggested_task_status="已完成", review_comment=""),
            current_user="owner",
            db=db,
        )

    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
