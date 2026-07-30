import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.routers.meetings import create_kickoff_run, create_meeting, review_kickoff_proposal
from app.database import Base
from app.services.kickoff_writeback import confirm_kickoff_start


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_confirm_start_rejects_pending_proposal():
    db = _db()
    db.add_all([models.Project(id=1, name="P", status="pending_kickoff"), models.KickoffAgentRun(id=1, project_id=1, status="submitted"), models.KickoffChangeProposal(run_id=1, proposal_type="update", target_type="task")])
    db.commit()
    with pytest.raises(HTTPException, match="未审核"):
        confirm_kickoff_start(1, "Coach", db)


def test_confirm_start_activates_after_approved_no_change():
    db = _db()
    db.add_all([models.Project(id=1, name="P", status="pending_kickoff"), models.KickoffAgentRun(id=1, project_id=1, status="submitted", result_json=json.dumps({"summary": "无调整"})), models.KickoffChangeProposal(run_id=1, proposal_type="no_change", target_type="", review_status="approved")])
    db.commit()
    project, meeting = confirm_kickoff_start(1, "Coach", db)
    assert project.status == "active"
    assert meeting.meeting_type == "kickoff"


def test_confirm_start_applies_an_approved_task_proposal_before_activation():
    db = _db()
    db.add_all([
        models.Project(id=1, name="P", status="pending_kickoff"),
        models.Task(id=10, project_id=1, key_task="Old title"),
        models.KickoffAgentRun(id=1, project_id=1, status="submitted", result_json=json.dumps({"summary": "调整"})),
        models.KickoffChangeProposal(
            run_id=1,
            proposal_type="update",
            target_type="task",
            target_id=10,
            proposed_json=json.dumps({"key_task": "New title"}),
            review_status="approved",
        ),
    ])
    db.commit()

    project, _meeting = confirm_kickoff_start(1, "Coach", db)

    assert project.status == "active"
    assert db.get(models.Task, 10).key_task == "New title"


def test_confirm_start_creates_an_approved_key_task_proposal():
    db = _db()
    db.add_all([
        models.Project(id=1, name="P", status="pending_kickoff"),
        models.Task(id=10, project_id=1, key_task="Workstream"),
        models.KickoffAgentRun(id=1, project_id=1, status="submitted", result_json=json.dumps({"summary": "新增任务"})),
        models.KickoffChangeProposal(
            run_id=1,
            proposal_type="create",
            target_type="subtask",
            proposed_json=json.dumps({"task_id": 10, "title": "New key task", "assignee": "Owner", "plan_time": "2026-08-01"}),
            review_status="approved",
        ),
    ])
    db.commit()

    confirm_kickoff_start(1, "Coach", db)

    created = db.query(models.SubTask).filter_by(task_id=10, title="New key task").one()
    assert created.assignee == "Owner"


def test_confirm_start_rejects_returned_proposal():
    db = _db()
    db.add_all([models.Project(id=1, name="P", status="pending_kickoff"), models.KickoffAgentRun(id=1, project_id=1, status="submitted"), models.KickoffChangeProposal(run_id=1, proposal_type="update", target_type="task", review_status="returned")])
    db.commit()
    with pytest.raises(HTTPException, match="退回"):
        confirm_kickoff_start(1, "Coach", db)


def test_run_creator_cannot_review_own_kickoff_proposal():
    db = _db()
    db.add_all([
        models.Person(id=1, name="Coach", is_active=True),
        models.Account(username="coach", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="P", status="pending_kickoff"),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Coach", role="project_ceo"),
        models.KickoffAgentRun(id=1, project_id=1, status="submitted", created_by_person_id=1),
        models.KickoffChangeProposal(id=1, run_id=1, proposal_type="no_change", target_type=""),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        review_kickoff_proposal(1, 1, schemas.KickoffProposalReviewPayload(status="approved"), current_user="coach", db=db)

    assert exc_info.value.status_code == 403


def test_pending_kickoff_project_rejects_normal_meeting_creation():
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="P", status="pending_kickoff"),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_meeting(schemas.MeetingPayload(project_id=1, title="Normal meeting"), current_user="owner", db=db)

    assert exc_info.value.status_code == 409


def test_active_project_rejects_a_second_kickoff_run_before_agent_execution():
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="P", status="active"),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_kickoff_run(1, schemas.KickoffRunCreatePayload(transcript_text="Kickoff"), current_user="owner", db=db)

    assert exc_info.value.status_code == 409
