from __future__ import annotations

import asyncio
import json
from datetime import date
from io import BytesIO

import pytest
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.services.project_meeting_agent import MeetingAgentError, MeetingAgentRunResult
from app.services.project_meeting_agent_contracts import MeetingAgentFinal, MeetingInfo
from app.services.project_meeting_agent_processing import (
    process_project_meeting_agent_run,
    project_meeting_run_status_payload,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _run(db: Session, *, status: str = "queued") -> models.ProjectMeetingRun:
    project = models.Project(id=1, name="Agent project", status="active", is_active=True)
    source = models.MeetingDocumentSource(
        id=2,
        project_id=1,
        original_name="weekly.docx",
        storage_key="1/weekly.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=12,
        content_hash="a" * 64,
    )
    snapshot = {
        "project_id": 1,
        "project": {"id": 1, "name": "Agent project"},
        "members": [],
        "workstreams": [],
        "recent_progress": [],
        "previous_meetings": [],
        "history": {"is_first_meeting": True, "previous_meeting_ids": []},
        "requested_meeting_type": "周会",
    }
    run = models.ProjectMeetingRun(
        id=3,
        project_id=1,
        document_source_id=2,
        snapshot_json=json.dumps(snapshot),
        document_text="会议主题：本周项目推进\n会议结论：继续完成验收。",
        status=status,
        stage="reading",
    )
    db.add_all([project, source, run])
    db.commit()
    return run


def _final() -> MeetingAgentFinal:
    return MeetingAgentFinal(
        meeting_info=MeetingInfo(
            title="", meeting_date="", meeting_type="", location="", host="",
            participants=[], organizer="", copied_to=[],
        ),
        meeting_info_evidence={}, summary="", summary_evidence=[], agenda_items=[], decisions=[],
        completed_items=[], next_steps=[], risks=[], open_questions=[], task_updates=[],
    )


def test_background_success_persists_agent_audit_then_waits_for_owner_review(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing

    monkeypatch.setattr(
        processing,
        "run_project_meeting_agent",
        lambda **_: MeetingAgentRunResult(
            final=_final(), trace=[{"tool": "get_project_profile"}], raw_responses=["{}"],
            invocation_log_ids=[17], events=[{"kind": "final"}], model_code="meeting-model", step_count=2,
        ),
    )

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    db.expire_all()
    run = db.get(models.ProjectMeetingRun, run.id)
    assert run.status == "pending_review"
    assert run.stage == "pending_review"
    assert run.step_count == 2
    assert run.model_code == "meeting-model"
    assert json.loads(run.invocation_log_ids_json) == [17]
    assert json.loads(run.raw_responses_json) == ["{}"]
    assert json.loads(run.tool_trace_json)["trace"] == [{"tool": "get_project_profile"}]
    assert json.loads(run.result_json)["meeting_draft"]["summary"] == ""
    meeting = db.query(models.Meeting).one()
    assert meeting.source_mode == "ai_analysis"
    assert meeting.review_status == "pending_review"
    assert meeting.publish_status == "draft"
    assert meeting.document_source_id == run.document_source_id
    assert db.query(models.MeetingChangeSet).filter_by(meeting_id=meeting.id).count() == 1


def test_background_agent_error_fails_without_fabricating_result(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing

    monkeypatch.setattr(
        processing,
        "run_project_meeting_agent",
        lambda **_: (_ for _ in ()).throw(MeetingAgentError(
            "invalid_model_output", "模型未返回有效会议结构", raw_responses=["not-json"],
            trace=[{"tool": "get_project_profile"}], invocation_log_ids=[18], events=[{"kind": "error"}],
        )),
    )

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    db.expire_all()
    run = db.get(models.ProjectMeetingRun, run.id)
    assert run.status == "failed"
    assert run.error_code == "invalid_model_output"
    assert "模型未返回有效会议结构" in run.error_message
    assert json.loads(run.result_json) == {}
    assert json.loads(run.raw_responses_json) == ["not-json"]


def test_status_payload_exposes_stage_steps_error_and_safe_audit_summary(db):
    run = _run(db, status="failed")
    run.stage = "analyzing"
    run.step_count = 3
    run.error_code = "provider_error"
    run.error_message = "模型服务暂不可用"
    run.model_code = "meeting-model"
    run.invocation_log_ids_json = "[8, 9]"
    run.tool_trace_json = json.dumps({"trace": [{"tool": "get_project_profile"}], "events": [{"kind": "model_response"}]})

    payload = project_meeting_run_status_payload(run)

    assert payload["status"] == "failed"
    assert payload["stage"] == "analyzing"
    assert payload["step_count"] == 3
    assert payload["error_code"] == "provider_error"
    assert payload["audit"] == {"model_code": "meeting-model", "invocation_log_ids": [8, 9], "event_count": 1, "tool_call_count": 1}


def test_create_route_queues_background_work_without_calling_model(db, monkeypatch, tmp_path):
    from app.routers import meetings
    import app.services.project_meeting_agent_processing as processing

    db.add_all([
        models.Project(id=1, name="Agent project", status="active", is_active=True),
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="test", person_id=1),
    ])
    db.commit()
    monkeypatch.setattr(meetings, "require_login", lambda user, _db: user)
    monkeypatch.setattr(meetings, "require_project_access", lambda *_: None)
    monkeypatch.setattr(meetings, "_project_meeting_document_root", lambda: tmp_path)
    monkeypatch.setattr(meetings, "save_meeting_document", lambda *_: {
        "original_name": "weekly.docx", "storage_key": "1/weekly.docx", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size_bytes": 10, "content_hash": "b" * 64,
    })
    monkeypatch.setattr(meetings, "extract_meeting_document_text", lambda *_: "会议结论：继续完成验收。")
    monkeypatch.setattr(processing, "process_project_meeting_agent_run", lambda *_: pytest.fail("model worker must not run in create request"))

    upload = UploadFile(filename="weekly.docx", file=BytesIO(b"word"))
    tasks = BackgroundTasks()
    payload = asyncio.run(meetings.create_project_meeting_document_run(
        background_tasks=tasks, project_id=1, meeting_type="周会", file=upload, current_user="owner", db=db,
    ))

    assert payload["status"] == "queued"
    assert payload["stage"] == "reading"
    assert len(tasks.tasks) == 1
    assert db.query(models.Meeting).count() == 0
