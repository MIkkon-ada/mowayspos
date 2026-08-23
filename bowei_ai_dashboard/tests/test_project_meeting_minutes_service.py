from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import Base
from app.domain import submission_status as SS
from app.domain import source_type as ST
from app.services.key_task_execution import record_execution_event
from app.services.meeting_document_storage import (
    MeetingDocumentStorageError,
    download_meeting_document_path,
    read_meeting_document,
    save_meeting_document,
)
import app.services.meeting_document_storage as meeting_document_storage
from app.services.project_meeting_minutes import (
    build_project_meeting_snapshot,
    normalize_project_meeting_agent_result,
    normalize_project_meeting_result,
    validate_execution_schedule_proposal,
)
from app.services.project_meeting_agent_contracts import (
    EvidenceSpan,
    MeetingAgentFinal,
    MeetingFact,
    MeetingInfo,
    TaskTarget,
    TaskUpdate,
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


def _confirmed_submission(
    db: Session,
    *,
    confirmed_at: datetime,
    created_at: datetime | None = None,
    cards: list[dict] | None = None,
    confirm_status: str = SS.S_CONFIRMED,
    source_type: str = ST.MANUAL,
) -> models.UpdateSubmission:
    submission = models.UpdateSubmission(
        project_id=1,
        source_type=source_type,
        submitter="Owner",
        submitter_id=1,
        title="Weekly report",
        transcript_text="Acceptance checklist reviewed",
        human_result_json=json.dumps({
            "task_reports": cards if cards is not None else [{
                "parent_task_id": 10,
                "matched_subtask_id": 20,
                "matched_subtask_title": "Weekly delivery",
                "match_status": "matched",
                "content": "Acceptance checklist reviewed",
                "actual_output": "Signed checklist",
                "next_step": "Prepare release",
            }],
        }),
        confirm_status=confirm_status,
        confirmed_at=confirmed_at,
        created_at=created_at,
    )
    db.add(submission)
    db.flush()
    return submission


def _confirmed_event(
    db: Session,
    *,
    occurred_at: datetime,
    source_id: int,
    authority: str = "confirmed",
) -> models.KeyTaskExecutionEvent:
    return record_execution_event(
        db,
        project_id=1,
        key_task_id=20,
        execution_plan_id=30,
        event_type="status_changed",
        source_type="work_report",
        source_id=source_id,
        dedupe_key=f"meeting-snapshot-{source_id}",
        actor_name="Owner",
        occurred_at=occurred_at,
        confirmed_at=occurred_at,
        effective_at=occurred_at,
        affects_current_progress=True,
        status_before="in_progress",
        status_after="completed",
        authority=authority,
    )


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

    assert snapshot["history"] == {"is_first_meeting": False, "previous_meeting_ids": [101]}
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


def test_snapshot_ignores_draft_and_returned_meetings_when_identifying_first_meeting(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    db.add_all([
        models.Meeting(id=111, project_id=project.id, title="Draft", publish_status="draft", review_status="pending_review"),
        models.Meeting(id=112, project_id=project.id, title="Returned", publish_status="draft", review_status="returned"),
    ])
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    assert snapshot["history"] == {"is_first_meeting": True, "previous_meeting_ids": []}
    assert snapshot["previous_meetings"] == []


def test_snapshot_freezes_only_confirmed_execution_facts_after_last_published_meeting_cutoff(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    published = models.Meeting(
        project_id=project.id,
        meeting_date="2026-07-27",
        publish_status="published",
    )
    approved_draft = models.Meeting(
        project_id=project.id,
        title="Approved draft meeting",
        meeting_date="2026-08-15",
        review_status="approved",
        publish_status="draft",
    )
    second_key_task = models.SubTask(
        id=22,
        task_id=10,
        title="Unreported delivery",
        assignee="Owner",
        assignee_id=1,
        status="not_started",
        plan_time="2026-08",
        completion_criteria="Release notes approved",
        notes="No confirmed updates yet",
    )
    second_schedule = models.ExecutionSchedule(
        id=32,
        subtask_id=second_key_task.id,
        plan_type="week",
        title="Draft release notes",
        status="not_started",
    )
    db.add_all([published, approved_draft, second_key_task, second_schedule])
    db.flush()
    submission = _confirmed_submission(
        db,
        created_at=datetime(2026, 8, 1, 1, 30),
        confirmed_at=datetime(2026, 8, 1, 2),
    )
    cutoff_utc = datetime(2026, 7, 27, 16, tzinfo=timezone.utc)
    before_cutoff = (cutoff_utc - timedelta(minutes=1)).replace(tzinfo=None)
    before_cutoff_submission = _confirmed_submission(
        db, confirmed_at=before_cutoff
    )
    _confirmed_event(db, occurred_at=datetime(2026, 8, 2, 3), source_id=100)
    before_cutoff_event = _confirmed_event(
        db,
        occurred_at=before_cutoff,
        source_id=101,
    )
    unconfirmed_submission = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 8, 3, 2),
        confirm_status=SS.S_NEW,
    )
    non_work_report_submission = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 8, 3, 2),
        source_type=ST.MEETING,
    )
    voice_submission = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 8, 3, 2),
        source_type=ST.VOICE,
    )
    document_submission = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 8, 3, 3),
        source_type=ST.DOCUMENT,
    )
    unconfirmed_event = _confirmed_event(
        db,
        occurred_at=datetime(2026, 8, 3, 3),
        source_id=102,
        authority="pending_confirmation",
    )
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    assert approved_draft.id in {
        item["meeting_id"] for item in snapshot["previous_meetings"]
    }
    assert snapshot["execution_window"] == {
        "start": "2026-07-28T00:00:00+08:00",
        "end": snapshot["execution_window"]["end"],
        "basis": "last_published_meeting_date",
        "last_published_meeting_id": published.id,
    }
    context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    second_context = snapshot["workstreams"][0]["key_tasks"][1]["execution_context"]
    assert set(context) == {
        "current_task_baseline",
        "current_execution_schedules",
        "confirmed_reports",
        "confirmed_events",
    }
    assert all(
        set(key_task["execution_context"]) == {
            "current_task_baseline",
            "current_execution_schedules",
            "confirmed_reports",
            "confirmed_events",
        }
        for key_task in snapshot["workstreams"][0]["key_tasks"]
    )
    assert context["current_task_baseline"] == {
        "id": 20,
        "title": "Weekly delivery",
        "assignee": "Owner",
        "assignee_id": 1,
        "status": "in_progress",
        "plan_time": "",
        "completion_criteria": "",
        "notes": "",
    }
    assert context["current_execution_schedules"] == snapshot["workstreams"][0]["key_tasks"][0]["execution_schedules"]
    assert context["current_execution_schedules"][0]["id"] == 30
    assert context["current_execution_schedules"][0]["title"] == "Finish acceptance checklist"
    assert context["current_execution_schedules"][0]["status"] == "in_progress"
    assert context["confirmed_reports"][0] == {
        "record_type": "confirmed_report",
        "source_type": "confirmed_report",
        "ingestion_source_type": ST.MANUAL,
        "source_submission_id": submission.id,
        "card_index": 0,
        "key_task_id": 20,
        "submitter": "Owner",
        "submitter_id": 1,
        "submitted_at": "2026-08-01T01:30:00",
        "confirmed_at": "2026-08-01T02:00:00",
        "confirmation_status": SS.S_CONFIRMED,
        "content": "Acceptance checklist reviewed",
        "actual_output": "Signed checklist",
        "next_step": "Prepare release",
    }
    assert {item["source_submission_id"] for item in context["confirmed_reports"]} == {
        submission.id,
        voice_submission.id,
        document_submission.id,
    }
    reports_by_submission_id = {
        item["source_submission_id"]: item for item in context["confirmed_reports"]
    }
    assert reports_by_submission_id[voice_submission.id]["source_type"] == "confirmed_report"
    assert reports_by_submission_id[voice_submission.id]["ingestion_source_type"] == ST.VOICE
    assert reports_by_submission_id[document_submission.id]["source_type"] == "confirmed_report"
    assert reports_by_submission_id[document_submission.id]["ingestion_source_type"] == ST.DOCUMENT
    assert [
        (
            item["status_before"],
            item["status_after"],
            item["record_type"],
            item["source_type"],
            item["source_id"],
        )
        for item in context["confirmed_events"]
    ] == [
        ("in_progress", "completed", "confirmed_event", "work_report", 100),
    ]
    assert before_cutoff_submission.id not in {
        item["source_submission_id"] for item in context["confirmed_reports"]
    }
    assert before_cutoff_event.id not in {item["event_id"] for item in context["confirmed_events"]}
    assert unconfirmed_submission.id not in {
        item["source_submission_id"] for item in context["confirmed_reports"]
    }
    assert non_work_report_submission.id not in {
        item["source_submission_id"] for item in context["confirmed_reports"]
    }
    assert unconfirmed_event.id not in {item["event_id"] for item in context["confirmed_events"]}
    assert second_context["current_task_baseline"] == {
        "id": 22,
        "title": "Unreported delivery",
        "assignee": "Owner",
        "assignee_id": 1,
        "status": "not_started",
        "plan_time": "2026-08",
        "completion_criteria": "Release notes approved",
        "notes": "No confirmed updates yet",
    }
    assert second_context["current_execution_schedules"] == snapshot["workstreams"][0]["key_tasks"][1]["execution_schedules"]
    assert second_context["current_execution_schedules"][0]["id"] == 32
    assert second_context["current_execution_schedules"][0]["title"] == "Draft release notes"
    assert second_context["current_execution_schedules"][0]["status"] == "not_started"
    assert second_context["confirmed_reports"] == []
    assert second_context["confirmed_events"] == []


def test_first_meeting_execution_window_uses_project_start_and_reports_missing_start(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    project.start_date = "2026-07-01"
    submission = _confirmed_submission(db, confirmed_at=datetime(2026, 7, 2, 2))
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    assert snapshot["execution_window"]["basis"] == "project_start_date"
    assert context["confirmed_reports"][0]["source_submission_id"] == submission.id

    project.start_date = ""
    db.commit()

    missing_start_snapshot = build_project_meeting_snapshot(project.id, db)

    missing_start_context = missing_start_snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    assert missing_start_snapshot["execution_window"] is None
    assert missing_start_context["confirmed_reports"] == []
    assert missing_start_context["confirmed_events"] == []
    assert missing_start_snapshot["diagnostics"] == [{"code": "missing_execution_window_start"}]


def test_first_meeting_execution_window_includes_same_shanghai_calendar_day_facts(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    project.start_date = "2026-07-01"
    report = _confirmed_submission(db, confirmed_at=datetime(2026, 6, 30, 16, 1))
    event = _confirmed_event(db, occurred_at=datetime(2026, 6, 30, 16, 2), source_id=103)
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    assert snapshot["execution_window"]["start"] == "2026-07-01T00:00:00+08:00"
    assert report.id in {item["source_submission_id"] for item in context["confirmed_reports"]}
    assert event.id in {item["event_id"] for item in context["confirmed_events"]}


def test_snapshot_excludes_invalid_confirmed_report_cards_with_diagnostics(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    project.start_date = "2026-07-01"
    invalid = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 7, 2, 2),
        cards=[{
            "parent_task_id": 10,
            "match_status": "matched",
            "content": "This card has no canonical key-task assignment",
        }],
    )
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    assert context["confirmed_reports"] == []
    assert snapshot["diagnostics"] == [{
        "code": "invalid_confirmed_report_card",
        "source_submission_id": invalid.id,
        "card_index": 0,
        "reason": "missing or invalid key-task assignment",
    }]


@pytest.mark.parametrize("invalid_key_task_id", [20.9, float("inf")])
def test_snapshot_rejects_non_integral_confirmed_report_ids_and_continues(
    db: Session,
    project_plan: tuple[models.Project, models.ExecutionSchedule],
    invalid_key_task_id: float,
):
    project, _ = project_plan
    project.start_date = "2026-07-01"
    submission = _confirmed_submission(
        db,
        confirmed_at=datetime(2026, 7, 2, 2),
        cards=[
            {
                "parent_task_id": 10,
                "matched_subtask_id": invalid_key_task_id,
                "match_status": "matched",
            },
            {
                "parent_task_id": 10,
                "matched_subtask_id": 20,
                "match_status": "matched",
                "content": "Valid card after an invalid historic card",
            },
        ],
    )
    db.commit()

    snapshot = build_project_meeting_snapshot(project.id, db)

    context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
    assert [(item["source_submission_id"], item["card_index"]) for item in context["confirmed_reports"]] == [
        (submission.id, 1),
    ]
    assert snapshot["diagnostics"] == [{
        "code": "invalid_confirmed_report_card",
        "source_submission_id": submission.id,
        "card_index": 0,
        "reason": "missing or invalid key-task assignment",
    }]


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
    assert proposal["target"]["key_task_id"] == 20
    assert proposal["target"]["workstream_id"] == 10
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


@pytest.mark.parametrize("target, expected_error", [
    ({"key_task_id": 999}, "key_task_id"),
    ({"subtask_id": 999}, "key_task_id"),
    ({"workstream_id": 999}, "workstream_id"),
])
def test_update_schedule_proposal_blocks_mismatched_explicit_parent_ids(
    db: Session,
    project_plan: tuple[models.Project, models.ExecutionSchedule],
    target: dict,
    expected_error: str,
):
    project, schedule = project_plan
    snapshot = build_project_meeting_snapshot(project.id, db)
    proposal = validate_execution_schedule_proposal(
        raw={
            "action": "update_execution_schedule",
            "target": {"project_id": project.id, "execution_schedule_id": schedule.id, **target},
            "proposed": {"status": "completed"},
            "evidence": ["Acceptance checklist approved"],
            "reason": "The meeting explicitly confirms approval.",
            "confidence": 0.9,
        },
        snapshot=snapshot,
        document_text="Acceptance checklist approved",
    )

    assert proposal["validation"]["state"] == "blocked"
    assert any(expected_error in error for error in proposal["validation"]["errors"])


def test_create_schedule_proposal_blocks_mismatched_explicit_workstream_id(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    snapshot = build_project_meeting_snapshot(project.id, db)
    proposal = validate_execution_schedule_proposal(
        raw={
            "action": "create_execution_schedule",
            "target": {"project_id": project.id, "key_task_id": 20, "workstream_id": 999},
            "proposed": {"plan_type": "week", "title": "New approved task"},
            "evidence": ["Create a new approved task"],
            "reason": "The meeting explicitly requests it.",
            "confidence": 0.9,
        },
        snapshot=snapshot,
        document_text="Create a new approved task",
    )

    assert proposal["target"]["key_task_id"] == 20
    assert proposal["target"]["workstream_id"] == 10
    assert proposal["validation"]["state"] == "blocked"
    assert any("workstream_id" in error for error in proposal["validation"]["errors"])


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


def _agent_evidence(document_text: str, quote: str) -> EvidenceSpan:
    start = document_text.index(quote)
    return EvidenceSpan(quote=quote, char_start=start, char_end=start + len(quote))


def _agent_final(document_text: str, **overrides) -> MeetingAgentFinal:
    meeting_info = MeetingInfo(
        title="AI Upgrade weekly meeting",
        meeting_date="2026-08-14",
        meeting_type="weekly meeting",
        location="online",
        host="Owner",
        participants=["Owner"],
        organizer="Owner",
        copied_to=["Project team"],
    )
    evidence = {
        field: [_agent_evidence(document_text, str(value))]
        for field, value in {
            "title": meeting_info.title,
            "meeting_date": meeting_info.meeting_date,
            "meeting_type": meeting_info.meeting_type,
            "location": meeting_info.location,
            "host": meeting_info.host,
            "participants": meeting_info.participants[0],
            "organizer": meeting_info.organizer,
            "copied_to": meeting_info.copied_to[0],
        }.items()
    }
    payload = {
        "meeting_info": meeting_info,
        "meeting_info_evidence": evidence,
        "summary": "Acceptance checklist is approved",
        "summary_evidence": [_agent_evidence(document_text, "Acceptance checklist is approved")],
        "agenda_items": [],
        "decisions": [],
        "completed_items": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
        "task_updates": [],
    }
    payload.update(overrides)
    return MeetingAgentFinal(**payload)


def _agent_document_text() -> str:
    return (
        "AI Upgrade weekly meeting\n2026-08-14\nweekly meeting\nonline\n"
        "Owner\nProject team\nAcceptance checklist is approved\n"
        "Move acceptance schedule to complete"
    )


def test_agent_normalization_returns_ready_validation_for_exact_meeting_metadata_evidence(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    document_text = _agent_document_text()

    result = normalize_project_meeting_agent_result(
        _agent_final(document_text), document_text, build_project_meeting_snapshot(project.id, db)
    )

    assert result["meeting_draft"]["title"] == "AI Upgrade weekly meeting"
    assert result["meeting_info_evidence"]["title"]["validation"]["state"] == "ready"
    assert result["meeting_info_evidence"]["meeting_date"]["validation"]["state"] == "ready"
    assert result["summary_evidence"]["validation"]["state"] == "ready"


def test_agent_normalization_preserves_evidence_grounded_action_columns(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    document_text = _agent_document_text() + "\nOwner: Move acceptance schedule to complete by 2026-08-14"
    action_quote = "Owner: Move acceptance schedule to complete by 2026-08-14"
    action = MeetingFact(
        content="Move acceptance schedule to complete",
        owner="Owner",
        due_date="2026-08-14",
        evidence=[_agent_evidence(document_text, action_quote)],
        confidence=0.9,
        needs_confirmation=False,
    )
    final = _agent_final(document_text, next_steps=[action])

    result = normalize_project_meeting_agent_result(
        final, document_text, build_project_meeting_snapshot(project.id, db)
    )

    assert result["next_stage_work"] == [{
        "content": "Move acceptance schedule to complete",
        "owner": "Owner",
        "tracker": "",
        "due_date": "2026-08-14",
        "confidence": 0.9,
        "needs_confirmation": False,
        "evidence": [{"quote": action_quote, "char_start": document_text.index(action_quote), "char_end": len(document_text)}],
        "validation": {"state": "ready", "errors": []},
    }]


def test_agent_normalization_corrects_a_unique_quote_with_wrong_character_range(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    document_text = _agent_document_text()
    final = _agent_final(document_text)
    wrong = final.meeting_info_evidence["title"][0].model_copy(update={"char_start": 1, "char_end": 1 + len("AI Upgrade weekly meeting")})
    final = final.model_copy(update={"meeting_info_evidence": {**final.meeting_info_evidence, "title": [wrong]}})

    result = normalize_project_meeting_agent_result(final, document_text, build_project_meeting_snapshot(project.id, db))

    evidence = result["meeting_info_evidence"]["title"]
    assert evidence["validation"]["state"] == "ready"
    assert evidence["evidence"][0]["char_start"] == document_text.index("AI Upgrade weekly meeting")


def test_agent_normalization_blocks_a_quote_that_is_not_in_the_document(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, _ = project_plan
    document_text = _agent_document_text()
    final = _agent_final(document_text)
    invalid = EvidenceSpan(quote="Missing title", char_start=0, char_end=len("Missing title"))
    final = final.model_copy(update={"meeting_info_evidence": {**final.meeting_info_evidence, "title": [invalid]}})

    result = normalize_project_meeting_agent_result(final, document_text, build_project_meeting_snapshot(project.id, db))

    assert result["meeting_info_evidence"]["title"]["validation"]["state"] == "blocked"
    assert any("quote" in error for error in result["meeting_info_evidence"]["title"]["validation"]["errors"])


def test_agent_normalization_blocks_task_update_without_exact_evidence(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan
    document_text = _agent_document_text()
    update = TaskUpdate(
        action="update_execution_schedule",
        target=TaskTarget(project_id=project.id, workstream_id=10, key_task_id=20, execution_schedule_id=schedule.id),
        before={"status": "in_progress"},
        proposed={"status": "completed"},
        evidence=[EvidenceSpan(quote="Not present", char_start=0, char_end=11)],
        reason="Meeting confirms completion",
        confidence=0.9,
        needs_confirmation=False,
    )

    result = normalize_project_meeting_agent_result(
        _agent_final(document_text, task_updates=[update]), document_text, build_project_meeting_snapshot(project.id, db)
    )

    assert result["execution_schedule_changes"][0]["validation"]["state"] == "blocked"
    assert any("quote" in error for error in result["execution_schedule_changes"][0]["validation"]["errors"])


def test_agent_normalization_requires_confirmation_when_only_confirmed_event_supports_schedule_update(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan
    document_text = _agent_document_text()
    project.start_date = "2026-08-01"
    _confirmed_event(db, occurred_at=datetime(2026, 8, 15, 1), source_id=104)
    db.commit()
    snapshot = build_project_meeting_snapshot(project.id, db)
    event = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]["confirmed_events"][0]
    update = TaskUpdate(
        action="update_execution_schedule",
        target=TaskTarget(project_id=project.id, workstream_id=10, key_task_id=20, execution_schedule_id=schedule.id),
        before={"status": "in_progress"},
        proposed={"status": "completed"},
        evidence=[EvidenceSpan(
            quote="Confirmed event records completed status",
            char_start=0,
            char_end=len("Confirmed event records completed status"),
        )],
        reason=f"confirmed_event {event['event_id']} records completed status",
        confidence=0.9,
        needs_confirmation=True,
    )

    result = normalize_project_meeting_agent_result(
        _agent_final(document_text, task_updates=[update]), document_text, snapshot
    )

    proposal = result["execution_schedule_changes"][0]
    assert proposal["validation"]["state"] == "needs_confirmation"
    assert "evidence" in " ".join(proposal["validation"]["errors"])


def test_agent_normalization_blocks_task_update_with_mismatched_workstream_parent(
    db: Session, project_plan: tuple[models.Project, models.ExecutionSchedule]
):
    project, schedule = project_plan
    document_text = _agent_document_text()
    update = TaskUpdate(
        action="update_execution_schedule",
        target=TaskTarget(project_id=project.id, workstream_id=999, key_task_id=20, execution_schedule_id=schedule.id),
        before={"status": "in_progress"},
        proposed={"status": "completed"},
        evidence=[_agent_evidence(document_text, "Move acceptance schedule to complete")],
        reason="Meeting confirms completion",
        confidence=0.9,
        needs_confirmation=False,
    )

    result = normalize_project_meeting_agent_result(
        _agent_final(document_text, task_updates=[update]), document_text, build_project_meeting_snapshot(project.id, db)
    )

    assert result["execution_schedule_changes"][0]["validation"]["state"] == "blocked"
    assert any("workstream_id" in error for error in result["execution_schedule_changes"][0]["validation"]["errors"])


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
