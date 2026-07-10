from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.projects import approve_project, owner_submit_project_profile


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_project_team(db):
    owner = models.Person(id=1, name="Owner Person", system_role="normal_member", is_active=True)
    coach = models.Person(id=2, name="Project Coach", system_role="normal_member", is_active=True)
    member = models.Person(id=3, name="Member Person", system_role="normal_member", is_active=True)
    company_ceo = models.Person(id=4, name="Company CEO", system_role="company_ceo", is_active=True)
    db.add_all(
        [
            owner,
            coach,
            member,
            company_ceo,
            models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
            models.Account(username="coach", password_hash="x", person_id=coach.id, status="active"),
            models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
            models.Account(username="company_ceo", password_hash="x", person_id=company_ceo.id, status="active"),
            models.Project(id=1, name="Draft Project", status="dispatched", is_active=False),
            models.ProjectMember(project_id=1, person_id=owner.id, person_name_snapshot=owner.name, role="owner"),
            models.ProjectMember(project_id=1, person_id=coach.id, person_name_snapshot=coach.name, role="project_ceo"),
            models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
        ]
    )
    db.commit()


def test_owner_submit_saves_work_progress_draft_without_activating_project():
    db = _make_session()
    _seed_project_team(db)

    payload = schemas.ProjectProfilePayload(
        objectives="Launch the pilot",
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Prepare pilot plan",
                description="Draft the execution plan",
                owner="Owner Person",
                helper="Member Person",
                plan_start="2026-08-01",
                plan_end="2026-08-10",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Confirm scope",
                        evaluation_standard="Scope signed off",
                        assignee="Owner Person",
                        helper="Member Person",
                        plan_start="2026-08-01",
                        plan_end="2026-08-03",
                    )
                ],
            )
        ],
    )

    result = owner_submit_project_profile(1, payload, current_user="owner", db=db)

    project = db.get(models.Project, 1)
    tasks = db.query(models.Task).filter_by(project_id=1).all()
    subtasks = db.query(models.SubTask).join(models.Task, models.SubTask.task_id == models.Task.id).filter(
        models.Task.project_id == 1
    ).all()

    assert result["submitted_for_review"] is True
    assert project.status == "pending_review"
    assert project.is_active is False
    assert len(tasks) == 1
    assert tasks[0].project_id == 1
    assert tasks[0].key_task == "Prepare pilot plan"
    assert tasks[0].completion_standard == "Draft the execution plan"
    assert tasks[0].owner == "Owner Person"
    assert tasks[0].collaborators == "Member Person"
    assert len(subtasks) == 1
    assert subtasks[0].task_id == tasks[0].id
    assert subtasks[0].title == "Confirm scope"
    assert subtasks[0].completion_criteria == "Scope signed off"
    assert subtasks[0].assignee == "Owner Person"
    assert "Member Person" in subtasks[0].notes


def test_non_owner_cannot_submit_project_init_work_progress_draft():
    db = _make_session()
    _seed_project_team(db)

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(
                work_progress_draft=[schemas.ProjectWorkProgressTaskDraft(title="Unauthorized task")]
            ),
            current_user="member",
            db=db,
        )

    assert exc.value.status_code == 403


def test_company_ceo_without_project_coach_role_cannot_approve_project():
    db = _make_session()
    _seed_project_team(db)
    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            work_progress_draft=[schemas.ProjectWorkProgressTaskDraft(title="Ready for review")]
        ),
        current_user="owner",
        db=db,
    )

    with pytest.raises(HTTPException) as exc:
        approve_project(1, schemas.ProjectProfilePayload(), current_user="company_ceo", db=db)

    assert exc.value.status_code == 403
