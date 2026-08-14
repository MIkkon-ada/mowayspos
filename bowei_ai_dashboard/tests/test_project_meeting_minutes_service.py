from __future__ import annotations

import hashlib
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import Base
from app.services.meeting_document_storage import (
    MeetingDocumentStorageError,
    download_meeting_document_path,
    read_meeting_document,
    save_meeting_document,
)
import app.services.meeting_document_storage as meeting_document_storage
from app.services.project_meeting_minutes import (
    build_project_meeting_snapshot,
    normalize_project_meeting_result,
    validate_execution_schedule_proposal,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def project_plan(db: Session) -> tuple[models.Project, models.ExecutionSchedule]:
    project = models.Project(id=1, name="AI Upgrade", status="active", is_active=True)
    owner = models.Person(id=1, name="Owner", is_active=True)
    inactive = models.Person(id=2, name="Inactive", is_active=False)
    task = models.Task(
        id=10,
        project_id=project.id,
        key_task="Delivery",
        owner="Owner",
        owner_id=owner.id,
        status="in_progress",
    )
    subtask = models.SubTask(
        id=20,
        task_id=task.id,
        title="Weekly delivery",
        assignee="Owner",
        assignee_id=owner.id,
        status="in_progress",
    )
    schedule = models.ExecutionSchedule(
        id=30,
        subtask_id=subtask.id,
        plan_type="week",
        plan_month="2026-08",
        title="Finish acceptance checklist",
        start_date=date(2026, 8, 10),
        due_date=date(2026, 8, 14),
        assignee="Owner",
        assignee_id=owner.id,
        status="in_progress",
        expected_output="Acceptance checklist",
        completion_criteria="Checklist is approved",
        progress_note="Half done",
        risk_dependency="Waiting for test data",
    )
    db.add_all(
        [
            project,
            owner,
            inactive,
            task,
            subtask,
            schedule,
            models.ProjectMember(project_id=project.id, person_id=owner.id, role="owner"),
            models.ProjectMember(project_id=project.id, person_id=inactive.id, role="member"),
        ]
    )
    db.commit()
    return project, schedule


def test_first_meeting_snapshot_contains_project_members_plan_and_schedules(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan

    snapshot = build_project_meeting_snapshot(project.id, db)

    assert snapshot["project"]["id"] == project.id
    assert snapshot["members"] == [
        {"person_id": 1, "name": "Owner", "role": "owner"}
    ]
    assert snapshot["workstreams"][0]["id"] == 10
    assert snapshot["workstreams"][0]["key_tasks"][0]["id"] == 20
    assert snapshot["workstreams"][0]["key_tasks"][0]["execution_schedules"] == [
        {
            "id": schedule.id,
            "plan_type": "week",
            "plan_month": "2026-08",
            "title": "Finish acceptance checklist",
            "start_date": "2026-08-10",
            "due_date": "2026-08-14",
            "assignee": "Owner",
            "assignee_id": 1,
            "status": "in_progress",
            "expected_output": "Acceptance checklist",
            "completion_criteria": "Checklist is approved",
            "progress_note": "Half done",
            "risk_dependency": "Waiting for test data",
            "actual_output": "",
            "delay_reason": "",
            "sort_order": 0,
            "collaborator_ids": [],
            "reminder_policy": {},
        }
    ]
    assert snapshot["history"] == {"is_first_meeting": True, "previous_meeting_ids": []}
    assert snapshot["recent_progress"] == [
        {
            "key_task_id": 20,
            "execution_schedule_id": schedule.id,
            "content": "Half done",
            "actual_output": "",
            "status": "in_progress",
            "updated_at": snapshot["recent_progress"][0]["updated_at"],
        }
    ]
    assert snapshot["previous_meetings"] == []


def test_snapshot_includes_only_current_project_progress_and_published_history(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan
    other_project = models.Project(id=2, name="Other", status="active", is_active=True)
    other_task = models.Task(id=11, project_id=2, key_task="Other stream", status="in_progress")
    other_key_task = models.SubTask(id=21, task_id=11, title="Other task", assignee="Other", status="in_progress")
    other_schedule = models.ExecutionSchedule(
        id=31,
        subtask_id=21,
        plan_type="week",
        title="Other progress",
        status="completed",
        progress_note="Must not leak",
        actual_output="Other output",
    )
    published = models.Meeting(
        id=101,
        project_id=project.id,
        title="Published meeting",
        meeting_date="2026-08-12",
        summary="Published summary",
        decision_items_json='[{"content": "Decision"}]',
        task_list_json='[{"content": "Action"}]',
        publish_status="published",
    )
    draft = models.Meeting(id=102, project_id=project.id, title="Draft meeting", publish_status="draft")
    foreign_published = models.Meeting(id=103, project_id=2, title="Foreign meeting", publish_status="published")
    db.add_all([other_project, other_task, other_key_task, other_schedule, published, draft, foreign_published])
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    assert snapshot["history"] == {"is_first_meeting": False, "previous_meeting_ids": [101, 102]}
    assert [item["execution_schedule_id"] for item in snapshot["recent_progress"]] == [schedule.id]
    assert snapshot["previous_meetings"] == [
        {
            "meeting_id": 101,
            "meeting_date": "2026-08-12",
            "title": "Published meeting",
            "summary": "Published summary",
            "decisions": [{"content": "Decision"}],
            "actions": [{"content": "Action"}],
        }
    ]


def test_schedule_proposal_accepts_only_contiguous_document_evidence(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan
    snapshot = build_project_meeting_snapshot(project.id, db)
    document_text = "本周已完成：验收清单已评审通过。"

    proposal = validate_execution_schedule_proposal(
        raw={
            "action": "update_execution_schedule",
            "target": {"project_id": project.id, "execution_schedule_id": schedule.id},
            "proposed": {"status": "completed", "actual_output": "验收清单已评审通过"},
            "evidence": ["验收清单已评审通过"],
            "reason": "会议原文明确说明验收清单已评审通过",
            "confidence": 0.95,
        },
        snapshot=snapshot,
        document_text=document_text,
    )

    assert proposal["validation"]["state"] == "ready"
    assert proposal["target"]["execution_schedule_id"] == schedule.id
    assert proposal["before"]["status"] == "in_progress"

    fabricated = validate_execution_schedule_proposal(
        raw={
            "action": "update_execution_schedule",
            "target": {"execution_schedule_id": schedule.id},
            "proposed": {"status": "completed"},
            "evidence": ["验收清单已完成"],
            "reason": "会议原文支持完成",
            "confidence": 0.9,
        },
        snapshot=snapshot,
        document_text=document_text,
    )

    assert fabricated["validation"]["state"] == "blocked"
    assert any("evidence" in error for error in fabricated["validation"]["errors"])


def test_normalized_result_blocks_fact_without_document_evidence(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    snapshot = build_project_meeting_snapshot(project.id, db)

    result = normalize_project_meeting_result(
        {
            "meeting_draft": {"summary": "会议确认验收清单已评审通过"},
            "facts": [
                {"type": "completed", "content": "验收清单已评审通过", "evidence": ["验收清单已评审通过"]},
                {"type": "completed", "content": "系统已上线", "evidence": ["系统已上线"]},
            ],
            "execution_schedule_changes": [],
        },
        document_text="会议确认验收清单已评审通过",
        snapshot=snapshot,
    )

    assert result["facts"][0]["validation"]["state"] == "ready"
    assert result["facts"][1]["validation"]["state"] == "blocked"
    assert any("evidence" in error for error in result["facts"][1]["validation"]["errors"])


def test_meeting_document_storage_hashes_reads_and_rejects_unsafe_inputs(tmp_path, monkeypatch):
    content = b"fake docx bytes"
    saved = save_meeting_document(tmp_path, 7, "minutes.docx", content)

    assert saved["storage_key"].startswith("7/")
    assert saved["content_hash"] == hashlib.sha256(content).hexdigest()
    assert read_meeting_document(tmp_path, saved["storage_key"]) == content
    assert download_meeting_document_path(tmp_path, saved["storage_key"]) == saved["path"]

    with pytest.raises(MeetingDocumentStorageError):
        save_meeting_document(tmp_path, 7, "minutes.pdf", content)
    with pytest.raises(MeetingDocumentStorageError):
        read_meeting_document(tmp_path, "../outside.docx")
    monkeypatch.setattr(meeting_document_storage, "MAX_MEETING_DOCUMENT_BYTES", 3)
    with pytest.raises(MeetingDocumentStorageError):
        save_meeting_document(tmp_path, 7, "large.docx", b"1234")
