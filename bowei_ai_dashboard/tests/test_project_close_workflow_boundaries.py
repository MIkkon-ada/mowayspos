import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers import projects


def test_projects_router_reexports_close_workflow_helpers():
    from app.services import project_close_workflow as workflow

    assert projects._lock_project_for_close is workflow.lock_project_for_close
    assert projects._lock_close_request is workflow.lock_close_request
    assert projects._close_request_response is workflow.close_request_response


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Owner", system_role="normal_member", is_active=True),
            models.Person(id=2, name="Coach", system_role="normal_member", is_active=True),
            models.Person(id=3, name="Outsider", system_role="normal_member", is_active=True),
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.Account(username="coach", password_hash="x", person_id=2, status="active"),
            models.Account(username="outsider", password_hash="x", person_id=3, status="active"),
            models.Project(id=1, name="Project", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Coach", role="project_ceo"),
        ]
    )
    db.commit()
    return db


def _payload() -> schemas.ProjectCloseRequestCreatePayload:
    return schemas.ProjectCloseRequestCreatePayload(
        summary="Complete",
        objective_result="Objectives achieved",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="Handover complete",
        retrospective="Retrospective complete",
    )


def _lifecycle_writer(project, status, *, db, project_id):
    project.status = status
    project.is_active = status == "active"
    return status


def test_close_workflow_create_edit_and_cancel_own_the_lifecycle_transition():
    from app.services import project_close_workflow as workflow

    db = _db()
    created = workflow.create_close_request(
        project_id=1,
        payload=_payload(),
        current_user="owner",
        db=db,
        lifecycle_writer=_lifecycle_writer,
    )
    assert created["status"] == "pending"
    assert db.get(models.Project, 1).status == "pending_close"

    updated = workflow.update_close_request(
        project_id=1,
        request_id=created["id"],
        payload=schemas.ProjectCloseRequestUpdatePayload(summary="Updated"),
        current_user="owner",
        db=db,
    )
    assert updated["summary"] == "Updated"

    cancelled = workflow.cancel_close_request(
        project_id=1,
        request_id=created["id"],
        current_user="owner",
        db=db,
        lifecycle_writer=_lifecycle_writer,
    )
    assert cancelled["status"] == "cancelled"
    assert db.get(models.Project, 1).status == "active"

    with pytest.raises(HTTPException) as exc_info:
        workflow.cancel_close_request(
            project_id=1,
            request_id=created["id"],
            current_user="owner",
            db=db,
            lifecycle_writer=_lifecycle_writer,
        )
    assert exc_info.value.status_code == 409


def test_close_workflow_reads_use_the_injected_view_authorizer():
    from app.services import project_close_workflow as workflow

    with pytest.raises(HTTPException) as exc_info:
        workflow.list_close_requests(
            project_id=1,
            status=None,
            current_user="outsider",
            db=_db(),
            view_authorizer=projects._require_close_request_view,
        )

    assert exc_info.value.status_code == 403
