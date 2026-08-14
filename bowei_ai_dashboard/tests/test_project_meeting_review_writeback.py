from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app import schemas
from app.routers.meetings import patch_meeting_change_proposal
from app.services import meeting_change_set


def _edit_lineage_proposal(**kwargs):
    editor = getattr(meeting_change_set, "edit_project_meeting_lineage_proposal", None)
    assert callable(editor), "lineage proposals need a dedicated audited owner-edit service"
    return editor(**kwargs)


def _execute_change_set(**kwargs):
    return meeting_change_set.execute_meeting_change_set(**kwargs)


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


def _snapshot(*, include_due_date: bool = True, key_task_status: str = "in_progress") -> dict:
    schedule = {
        "id": 30,
        "plan_type": "week",
        "plan_month": "2026-08",
        "title": "First customer batch",
        "start_date": "2026-08-01",
        "status": "in_progress",
        "risk_dependency": "",
    }
    if include_due_date:
        schedule["due_date"] = "2026-08-10"
    return {
        "project_id": 1,
        "workstreams": [{
            "id": 10,
            "key_tasks": [{
                "id": 20,
                "title": "Customer list",
                "status": key_task_status,
                "execution_schedules": [schedule],
            }],
        }],
    }


def _result(action: str, proposed: dict, target: dict) -> dict:
    field_sources = {
        field: {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}
        for field in proposed
    }
    fields = {
        field: {
            "value": value,
            "raw_text": str(value),
            "evidence": [{"quote": str(value), "char_start": 0, "char_end": len(str(value))}],
            "provenance": source,
        }
        for field, (value, source) in ((name, (value, field_sources[name])) for name, value in proposed.items())
    }
    return {
        "meeting_facts": [{"fact_id": "F001", "fields": fields}],
        "project_matches": [{
            "match_id": "M001", "fact_id": "F001", "target_type": "execution_schedule" if action.startswith("update") else "key_task",
            "target_id": target.get("execution_schedule_id", target["key_task_id"]),
            "workstream_id": 10, "key_task_id": 20, "project_evidence": [],
        }],
        "project_deltas": [{
            "delta_id": "D001", "source_fact_id": "F001", "source_match_id": "M001", "delta_type": "PROGRESS_UPDATE", "reasoning": "baseline",
        }],
        "proposed_changes": [{
            "change_id": "C001", "source_fact_id": "F001", "source_match_id": "M001", "source_delta_id": "D001",
            "action": action, "target": target, "proposed": proposed,
            "field_sources": field_sources, "requires_confirmation": True,
        }],
    }


def _lineage(action: str, proposed: dict, target: dict, snapshot: dict) -> dict:
    before_baseline = {field: _snapshot_value(snapshot, field) for field in proposed} if action.startswith("update") else {}
    return {
        "schema_version": 1,
        "action": action,
        "target": target,
        "requires_confirmation": True,
        "change_id": "C001",
        "source_fact_id": "F001",
        "source_match_id": "M001",
        "source_delta_id": "D001",
        "field_sources": {
            field: {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}
            for field in proposed
        },
        "meeting_evidence": {field: [{"quote": str(value), "char_start": 0, "char_end": len(str(value))}] for field, value in proposed.items()},
        "project_evidence": [],
        "delta": {"delta_id": "D001", "source_fact_id": "F001", "source_match_id": "M001", "delta_type": "PROGRESS_UPDATE", "reasoning": "baseline"},
        "before_baseline": before_baseline,
        "baseline_state": "existing_target" if action.startswith("update") else "not_applicable_new_object",
        "parent_baseline": {"project_id": 1, "workstream_id": 10, "key_task_id": 20, "key_task": snapshot["workstreams"][0]["key_tasks"][0]},
        "owner_edit_history": [],
    }


def _snapshot_value(snapshot: dict, field: str):
    return snapshot["workstreams"][0]["key_tasks"][0]["execution_schedules"][0].get(field)


def _seed(
    db: Session,
    *,
    action: str = "update_execution_schedule",
    proposed: dict | None = None,
    include_due_date: bool = True,
) -> tuple[models.Meeting, models.MeetingChangeSet, models.MeetingChangeProposal, models.ProjectMeetingRun]:
    proposed = proposed or {"status": "completed"}
    snapshot = _snapshot(include_due_date=include_due_date)
    target = {"project_id": 1, "workstream_id": 10, "key_task_id": 20}
    if action.startswith("update"):
        target["execution_schedule_id"] = 30
    result = _result(action, proposed, target)
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(id=1, username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
        models.Task(id=10, project_id=1, key_task="Delivery", owner="Owner", status="in_progress"),
        models.SubTask(id=20, task_id=10, title="Customer list", assignee="Owner", status="in_progress"),
        models.ExecutionSchedule(id=30, subtask_id=20, plan_type="week", plan_month="2026-08", title="First customer batch", start_date=date(2026, 8, 1), due_date=date(2026, 8, 10), status="in_progress", created_by="owner", updated_by="owner"),
        models.MeetingDocumentSource(id=2, project_id=1, original_name="weekly.docx", storage_key="1/weekly.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", size_bytes=1, content_hash="a" * 64),
        models.ProjectMeetingRun(id=3, project_id=1, document_source_id=2, snapshot_json=json.dumps(snapshot), result_json=json.dumps(result), document_text="completed", status="pending_review"),
        models.Meeting(id=1, project_id=1, title="Weekly", publish_status="published", document_source_id=2),
    ])
    db.flush()
    change_set = models.MeetingChangeSet(id=4, project_id=1, meeting_id=1, snapshot_json=json.dumps(snapshot), result_json=json.dumps(result), status="draft")
    db.add(change_set)
    db.flush()
    proposal = models.MeetingChangeProposal(
        id=5, change_set_id=4, action=action, target_type="execution_schedule",
        target_id=30 if action.startswith("update") else None, parent_workstream_id=10, parent_subtask_id=20,
        before_json=json.dumps({field: _snapshot_value(snapshot, field) for field in proposed} if action.startswith("update") else {}),
        proposed_json=json.dumps(proposed), evidence_json="[]", reason="baseline", confidence=0.9,
        validation_json=json.dumps({"state": "ready", "errors": []}), lineage_json=json.dumps(_lineage(action, proposed, target, snapshot)), execution_status="pending",
    )
    db.add(proposal)
    db.commit()
    return db.get(models.Meeting, 1), change_set, proposal, db.get(models.ProjectMeetingRun, 3)


def test_owner_edit_preserves_immutable_result_and_allows_lineage_writeback(db):
    meeting, change_set, proposal, run = _seed(db)
    original_result = run.result_json

    _edit_lineage_proposal(
        proposal=proposal, change_set=change_set, meeting=meeting, actor="owner",
        proposed_updates={"due_date": "2026-08-03"}, db=db,
    )
    lineage = json.loads(proposal.lineage_json)
    assert lineage["field_sources"]["due_date"] == {"source_type": "human_edit", "usage": "override"}
    assert lineage["before_baseline"]["due_date"] == "2026-08-10"
    assert lineage["owner_edit_history"][-1]["after"] == "2026-08-03"
    _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.ExecutionSchedule, 30).due_date == date(2026, 8, 3)
    assert db.get(models.ProjectMeetingRun, run.id).result_json == original_result


def test_update_owner_added_field_requires_frozen_target_baseline(db):
    meeting, change_set, proposal, _ = _seed(db, include_due_date=False)
    with pytest.raises(HTTPException, match="frozen baseline"):
        _edit_lineage_proposal(
            proposal=proposal, change_set=change_set, meeting=meeting, actor="owner",
            proposed_updates={"due_date": "2026-08-03"}, db=db,
        )


def test_create_owner_added_field_has_not_applicable_target_baseline(db):
    meeting, change_set, proposal, _ = _seed(db, action="create_execution_schedule", proposed={"title": "Second customer batch"})
    _edit_lineage_proposal(
        proposal=proposal, change_set=change_set, meeting=meeting, actor="owner",
        proposed_updates={"due_date": "2026-08-03"}, db=db,
    )
    lineage = json.loads(proposal.lineage_json)
    assert lineage["baseline_state"] == "not_applicable_new_object"
    assert "due_date" not in lineage["before_baseline"]
    assert lineage["field_sources"]["due_date"]["source_type"] == "human_edit"


def test_update_allows_unrelated_live_field_change(db):
    meeting, _, proposal, _ = _seed(db)
    db.get(models.ExecutionSchedule, 30).risk_dependency = "unrelated live change"
    db.commit()
    _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert proposal.execution_status == "executed"


def test_update_touched_live_field_change_marks_conflict_without_write(db):
    meeting, _, proposal, _ = _seed(db)
    db.get(models.ExecutionSchedule, 30).status = "changed"
    db.commit()
    with pytest.raises(HTTPException, match="conflict"):
        _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.MeetingChangeProposal, proposal.id).execution_status == "conflict"
    assert db.get(models.ExecutionSchedule, 30).status == "changed"


def test_create_conflicts_on_changed_parent_or_duplicate_schedule(db):
    meeting, _, proposal, _ = _seed(db, action="create_execution_schedule", proposed={"title": "Second customer batch", "plan_type": "week"})
    db.get(models.SubTask, 20).status = "completed"
    db.commit()
    with pytest.raises(HTTPException, match="conflict"):
        _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.MeetingChangeProposal, proposal.id).execution_status == "conflict"


def test_create_duplicate_schedule_marks_conflict(db):
    meeting, _, proposal, _ = _seed(db, action="create_execution_schedule", proposed={"title": "First customer batch", "plan_type": "week", "plan_month": "2026-08"})
    with pytest.raises(HTTPException, match="conflict"):
        _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.MeetingChangeProposal, proposal.id).execution_status == "conflict"


def test_owner_only_patch_records_edit_history_in_review_payload(db):
    meeting, change_set, proposal, _ = _seed(db)
    response = patch_meeting_change_proposal(
        meeting.id,
        proposal.id,
        schemas.MeetingChangeProposalPatch(proposed={"due_date": "2026-08-03"}),
        current_user="owner",
        db=db,
    )
    assert response["lineage"]["owner_edit_history"][-1]["field"] == "due_date"
    assert response["lineage"]["baseline_state"] == "existing_target"

    db.add_all([
        models.Person(id=2, name="Member", is_active=True),
        models.Account(id=2, username="member", password_hash="x", person_id=2, status="active"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Member", role="member"),
    ])
    db.commit()
    with pytest.raises(HTTPException, match="permission"):
        patch_meeting_change_proposal(
            meeting.id,
            proposal.id,
            schemas.MeetingChangeProposalPatch(proposed={"due_date": "2026-08-04"}),
            current_user="member",
            db=db,
        )


def test_tampered_lineage_or_missing_human_edit_history_cannot_write(db):
    meeting, _, proposal, _ = _seed(db)
    lineage = json.loads(proposal.lineage_json)
    lineage["field_sources"]["status"]["source_fact_id"] = "F999"
    proposal.lineage_json = json.dumps(lineage)
    db.commit()
    with pytest.raises(HTTPException, match="conflict"):
        _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.MeetingChangeProposal, proposal.id).execution_status == "conflict"


def test_human_edit_without_server_history_cannot_write(db):
    meeting, _, proposal, _ = _seed(db)
    lineage = json.loads(proposal.lineage_json)
    lineage["field_sources"]["status"] = {"source_type": "human_edit", "usage": "override"}
    proposal.proposed_json = json.dumps({"status": "blocked"})
    proposal.lineage_json = json.dumps(lineage)
    db.commit()
    with pytest.raises(HTTPException, match="conflict"):
        _execute_change_set(meeting=meeting, proposal_ids=[proposal.id], actor="owner", db=db)
    assert db.get(models.MeetingChangeProposal, proposal.id).execution_status == "conflict"
