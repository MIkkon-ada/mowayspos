from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, schemas
from app.database import Base
from app.services import meeting_change_set_review_workflow as workflow


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_ordinary_change_set(
    db: Session,
) -> tuple[models.Meeting, models.MeetingChangeSet, models.MeetingChangeProposal]:
    snapshot = {
        "project_id": 1,
        "workstreams": [{
            "id": 10,
            "subtasks": [{
                "id": 20,
                "title": "Customer list",
                "assignee": "Owner",
                "plan_time": "",
                "completion_criteria": "",
                "status": "in_progress",
                "notes": "Before meeting",
            }],
        }],
    }
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(
            id=1,
            username="owner",
            password_hash="x",
            person_id=1,
            status="active",
        ),
        models.Project(id=1, name="Project A", status="active", is_active=True),
        models.ProjectMember(
            project_id=1,
            person_id=1,
            person_name_snapshot="Owner",
            role="owner",
        ),
        models.Task(
            id=10,
            project_id=1,
            key_task="Delivery",
            owner="Owner",
            status="in_progress",
        ),
        models.SubTask(
            id=20,
            task_id=10,
            title="Customer list",
            assignee="Owner",
            status="in_progress",
            notes="Before meeting",
        ),
        models.Meeting(
            id=1,
            project_id=1,
            creator_person_id=1,
            title="Weekly review",
            transcript_text="Meeting evidence.",
            publish_status="published",
        ),
    ])
    db.flush()
    change_set = models.MeetingChangeSet(
        id=1,
        project_id=1,
        meeting_id=1,
        snapshot_json=json.dumps(snapshot),
        result_json="{}",
        status="draft",
    )
    proposal = models.MeetingChangeProposal(
        id=1,
        change_set_id=1,
        action="update_subtask",
        target_type="subtask",
        target_id=20,
        parent_workstream_id=10,
        before_json=json.dumps({"notes": "Before meeting"}),
        proposed_json=json.dumps({"notes": "Before meeting"}),
        evidence_json=json.dumps(["Meeting evidence."]),
        reason="The meeting explicitly reviewed the note.",
        confidence=0.9,
        validation_json=json.dumps({"state": "ready", "errors": []}),
        execution_status="pending",
    )
    db.add_all([change_set, proposal])
    db.commit()
    return db.get(models.Meeting, 1), db.get(models.MeetingChangeSet, 1), db.get(models.MeetingChangeProposal, 1)


def test_review_workflow_reads_and_revalidates_an_ordinary_proposal(db: Session):
    meeting, change_set, proposal = _seed_ordinary_change_set(db)

    result = workflow.get_meeting_change_set(
        row_id=meeting.id,
        current_user="owner",
        db=db,
    )

    assert result["id"] == change_set.id
    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["target"] == {
        "project_id": 1,
        "subtask_id": proposal.target_id,
        "parent_workstream_id": proposal.parent_workstream_id,
    }

    patched = workflow.patch_meeting_change_proposal(
        row_id=meeting.id,
        proposal_id=proposal.id,
        payload=schemas.MeetingChangeProposalPatch(
            proposed={"notes": "Human reviewed notes"},
            evidence=["Meeting evidence."],
            reason="Human reviewed the exact note.",
        ),
        current_user="owner",
        db=db,
    )

    assert patched["proposed"] == {"notes": "Human reviewed notes"}
    assert patched["validation"]["state"] == "ready"
