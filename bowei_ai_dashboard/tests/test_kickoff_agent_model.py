from app import models
from app.domain import project_lifecycle as PL
from app.routers.projects import approve_project
from app.routers.subtasks import _check_subtask_struct_write
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base


def test_pending_kickoff_has_a_canonical_lifecycle_and_audit_models():
    assert PL.normalize("pending_kickoff") == "pending_kickoff"
    assert "pending_kickoff" in PL.ALL_STATUSES
    assert models.KickoffAgentRun.__tablename__ == "kickoff_agent_runs"
    assert models.KickoffChangeProposal.__tablename__ == "kickoff_change_proposals"


def test_project_approval_enters_pending_kickoff_without_starting_project():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    coach = models.Person(id=1, name="Coach", system_role="normal_member", is_active=True)
    db.add_all([
        coach,
        models.Account(username="coach", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="P", status="pending_review", is_active=False),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Coach", role="project_ceo"),
    ])
    db.commit()

    approve_project(1, current_user="coach", db=db)

    project = db.get(models.Project, 1)
    assert project.status == "pending_kickoff"
    assert project.is_active is False


def test_pending_kickoff_rejects_execution_task_structure_write():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Project(id=1, name="P", status="pending_kickoff", is_active=False),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
        models.Task(id=1, project_id=1, key_task="Work"),
    ])
    db.commit()

    try:
        _check_subtask_struct_write({"person_id": 1, "is_tech_admin": False}, db.get(models.Task, 1), db)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("pending kickoff must reject execution task writes")
