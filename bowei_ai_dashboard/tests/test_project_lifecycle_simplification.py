from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.domain import project_lifecycle as PL
from app.routers import projects


def _db(status: str = "draft"):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Company CEO", system_role="company_ceo", is_active=True),
            models.Person(id=2, name="Owner", system_role="normal_member", is_active=True),
            models.Person(id=3, name="Coach", system_role="normal_member", is_active=True),
            models.Account(username="company_ceo", password_hash="x", person_id=1, status="active"),
            models.Account(username="owner", password_hash="x", person_id=2, status="active"),
            models.Account(username="coach", password_hash="x", person_id=3, status="active"),
            models.Project(id=1, name="Project", status=status, is_active=status == "active"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Coach", role="project_ceo"),
        ]
    )
    db.commit()
    return db


def test_approval_enters_active_without_pending_kickoff_gate():
    db = _db("pending_review")

    result = projects.approve_project(1, current_user="coach", db=db)

    assert result["status"] == "active"
    project = db.get(models.Project, 1)
    assert project.status == "active"
    assert project.is_active is True


def test_dispatch_notifies_owner_without_changing_lifecycle():
    db = _db("draft")

    result = projects.dispatch_project(1, current_user="company_ceo", db=db)

    assert result["ok"] is True
    assert result["notified_to"] == 1
    assert result["status"] == "draft"
    assert db.get(models.Project, 1).status == "draft"
    assert db.query(models.Notification).filter_by(type="project_owner_notify", project_id=1).count() == 1


def test_owner_submission_still_accepts_draft_without_dispatch_state():
    db = _db("draft")

    result = projects.owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(objectives="目标"),
        current_user="owner",
        db=db,
    )

    assert result["status"] == "pending_review"
    assert db.get(models.Project, 1).status == "pending_review"


def test_legacy_lifecycle_states_are_classified_for_compatibility():
    assert PL.is_execution_available("active") is True
    assert PL.is_execution_available("pending_kickoff") is True
    assert PL.is_owner_plan_editable("draft") is True
    assert PL.is_owner_plan_editable("dispatched") is True
    assert PL.is_owner_plan_editable("returned") is True
