from __future__ import annotations

import asyncio
import json
from datetime import date
from io import BytesIO
from pathlib import Path

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
        "workstreams": [{
            "id": 10,
            "key_task": "Delivery",
            "key_tasks": [{
                "id": 20,
                "title": "Customer list",
                "status": "in_progress",
                "execution_schedules": [{
                    "id": 30,
                    "title": "Customer list first batch",
                    "status": "in_progress",
                    "due_date": "2026-08-20",
                }],
            }],
        }],
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
        document_text="客户清单已经完成，客户清单第二批需要创建。",
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


def _span(document_text: str, quote: str) -> dict[str, int | str]:
    start = document_text.index(quote)
    return {"quote": quote, "char_start": start, "char_end": start + len(quote)}


def _analysis_final(document_text: str, *, action: str = "update_execution_schedule", trusted: bool = True) -> MeetingAgentFinal:
    payload = _final().model_dump(mode="json")
    if action == "update_execution_schedule":
        fact_type, fact_content, field_name, raw_text, value = "completion", "客户清单已经完成", "status", "已经完成", "completed"
        match = {
            "match_id": "M001", "fact_id": "F001", "target_type": "execution_schedule", "target_id": 30,
            "workstream_id": 10, "key_task_id": 20, "confidence": 0.9, "reasons": ["title match"],
            "project_evidence": [{"source_object": "execution_schedule:30", "field": "title", "value": "Customer list first batch"}],
        }
        delta_type = "PROGRESS_UPDATE"
        target = {"project_id": 1, "workstream_id": 10, "key_task_id": 20, "execution_schedule_id": 30}
        before = {"status": "in_progress"}
    else:
        fact_type, fact_content, field_name, raw_text, value = "action_item", "客户清单第二批", "title", "客户清单第二批", "客户清单第二批"
        match = {
            "match_id": "M001", "fact_id": "F001", "target_type": "key_task", "target_id": 20,
            "workstream_id": 10, "key_task_id": 20, "confidence": 0.9, "reasons": ["parent match"],
            "project_evidence": [{"source_object": "key_task:20", "field": "title", "value": "Customer list"}],
        }
        delta_type = "NEW_EXECUTION_SCHEDULE"
        target = {"project_id": 1, "workstream_id": 10, "key_task_id": 20}
        before = {}
    fact = {
        "fact_id": "F001", "fact_type": fact_type, "content": fact_content,
        "fields": {
            field_name: {
                "value": value, "raw_text": raw_text, "evidence": [_span(document_text, raw_text)],
                "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
            }
        },
        "meeting_evidence": [_span(document_text, fact_content)], "confidence": 0.9, "needs_confirmation": False,
    }
    if not trusted:
        match["target_id"] = 999
    payload.update({
        "meeting_facts": [fact],
        "project_matches": [match],
        "project_deltas": [{"delta_id": "D001", "source_fact_id": "F001", "source_match_id": "M001", "delta_type": delta_type, "reasoning": "baseline comparison"}],
        "proposed_changes": [{
            "change_id": "C001", "source_fact_id": "F001", "source_match_id": "M001", "source_delta_id": "D001",
            "action": action, "target": target, "before": before, "proposed": {field_name: value},
            "field_sources": {field_name: {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}},
            "requires_confirmation": True,
        }],
    })
    return MeetingAgentFinal.model_validate(payload)


def _agent_result(final: MeetingAgentFinal) -> MeetingAgentRunResult:
    return MeetingAgentRunResult(
        final=final, trace=[{"tool": "search_plan_nodes"}], raw_responses=["{}"],
        invocation_log_ids=[17], events=[{"kind": "final"}], model_code="meeting-model", step_count=2,
    )


def test_meeting_change_proposal_lineage_schema_and_migration_are_declared():
    column = models.MeetingChangeProposal.__table__.c.lineage_json
    assert column.default.arg == "{}"
    assert str(column.server_default.arg) == "{}"
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "d5e6f7a8b9c0_add_meeting_proposal_lineage.py"
    assert migration.exists()
    assert 'down_revision = "c4e5f6a7b8c9"' in migration.read_text(encoding="utf-8")


def test_background_success_persists_trusted_update_lineage_and_immutable_result(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing
    monkeypatch.setattr(processing, "run_project_meeting_agent", lambda **_: _agent_result(_analysis_final(run.document_text)))

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    db.expire_all()
    persisted_run = db.get(models.ProjectMeetingRun, run.id)
    change_set = db.query(models.MeetingChangeSet).one()
    proposal = db.query(models.MeetingChangeProposal).one()
    result = json.loads(persisted_run.result_json)
    lineage = json.loads(proposal.lineage_json)
    assert result == json.loads(change_set.result_json)
    assert result["meeting_draft"]["summary"] == ""
    assert result["meeting_facts"][0]["fact_id"] == "F001"
    assert result["proposed_changes"][0]["change_id"] == "C001"
    assert lineage["schema_version"] == 1
    assert lineage["change_id"] == "C001"
    assert lineage["source_fact_id"] == "F001"
    assert lineage["source_match_id"] == "M001"
    assert lineage["source_delta_id"] == "D001"
    assert lineage["field_sources"]["status"]["source_type"] == "meeting_fact"
    assert lineage["meeting_evidence"]["status"][0]["quote"] == "已经完成"
    assert lineage["project_evidence"][0]["source_object"] == "execution_schedule:30"
    assert lineage["delta"]["delta_id"] == "D001"
    assert lineage["baseline_state"] == "existing_target"
    assert lineage["before_baseline"] == {"status": "in_progress"}
    assert lineage["owner_edit_history"] == []
    assert db.query(models.MeetingChangeProposal).count() == 1
    assert db.query(models.ExecutionSchedule).count() == 0


def test_standard_meeting_category_is_persisted_without_rewriting_word_result(db, monkeypatch):
    run = _run(db)
    snapshot = json.loads(run.snapshot_json)
    snapshot["requested_meeting_type"] = "special"
    run.snapshot_json = json.dumps(snapshot)
    run.document_text += " Word 原文专题名称"
    db.commit()

    final_payload = _analysis_final(run.document_text).model_dump(mode="json")
    final_payload["meeting_info"]["meeting_type"] = "Word 原文专题名称"
    final_payload["meeting_info_evidence"]["meeting_type"] = [_span(run.document_text, "Word 原文专题名称")]
    final = MeetingAgentFinal.model_validate(final_payload)
    import app.services.project_meeting_agent_processing as processing
    monkeypatch.setattr(processing, "run_project_meeting_agent", lambda **_: _agent_result(final))

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    db.expire_all()
    meeting = db.query(models.Meeting).one()
    persisted_run = db.get(models.ProjectMeetingRun, run.id)
    assert meeting.meeting_type == "special"
    assert json.loads(persisted_run.result_json)["meeting_draft"]["meeting_type"] == "Word 原文专题名称"


def test_background_success_persists_create_parent_baseline_without_target_baseline(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing
    monkeypatch.setattr(
        processing,
        "run_project_meeting_agent",
        lambda **_: _agent_result(_analysis_final(run.document_text, action="create_execution_schedule")),
    )

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    proposal = db.query(models.MeetingChangeProposal).one()
    lineage = json.loads(proposal.lineage_json)
    assert lineage["baseline_state"] == "not_applicable_new_object"
    assert lineage["before_baseline"] == {}
    assert lineage["parent_baseline"]["key_task_id"] == 20
    assert lineage["parent_baseline"]["key_task"]["title"] == "Customer list"
    assert lineage["owner_edit_history"] == []


def test_background_does_not_create_proposal_for_untrusted_analysis_change(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing
    monkeypatch.setattr(processing, "run_project_meeting_agent", lambda **_: _agent_result(_analysis_final(run.document_text, trusted=False)))

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    assert db.query(models.MeetingChangeProposal).count() == 0


def test_background_does_not_create_proposal_for_unknown_execution_schedule_field(db, monkeypatch):
    run = _run(db)
    import app.services.project_meeting_agent_processing as processing
    payload = _analysis_final(run.document_text).model_dump(mode="json")
    payload["meeting_facts"][0]["fields"] = {
        "lifecycle_status": {
            "value": "已经完成", "raw_text": "已经完成", "evidence": [_span(run.document_text, "已经完成")],
            "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
        }
    }
    payload["proposed_changes"][0]["proposed"] = {"lifecycle_status": "已经完成"}
    payload["proposed_changes"][0]["field_sources"] = {
        "lifecycle_status": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}
    }
    monkeypatch.setattr(
        processing,
        "run_project_meeting_agent",
        lambda **_: _agent_result(MeetingAgentFinal.model_validate(payload)),
    )

    process_project_meeting_agent_run(run.id, session_factory=sessionmaker(bind=db.get_bind()))

    db.expire_all()
    persisted_run = db.get(models.ProjectMeetingRun, run.id)
    assert json.loads(persisted_run.result_json)["proposed_changes"][0]["validation"]["state"] == "blocked"
    assert db.query(models.MeetingChangeProposal).count() == 0


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
