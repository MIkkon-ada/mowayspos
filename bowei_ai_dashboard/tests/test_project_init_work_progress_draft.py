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


def _add_people_for_picker(db):
    db.add_all(
        [
            models.Person(id=5, name="New Assignee", system_role="normal_member", is_active=True),
            models.Person(id=6, name="Helper One", system_role="normal_member", is_active=True),
            models.Person(id=7, name="Helper Two", system_role="normal_member", is_active=True),
        ]
    )
    db.commit()


def test_owner_submit_adds_selected_people_to_project_and_snapshots_names():
    db = _make_session()
    _seed_project_team(db)
    _add_people_for_picker(db)

    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="Selected people task",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title="Selected key task",
                            assignee_id=5,
                            helper_ids=[6, 7, 6],
                        )
                    ],
                )
            ]
        ),
        current_user="owner",
        db=db,
    )

    members = db.query(models.ProjectMember).filter_by(project_id=1).all()
    subtasks = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).all()
    assert {(m.person_id, m.role) for m in members} >= {(5, "member"), (6, "member"), (7, "member")}
    assert len([m for m in members if m.person_id == 6 and m.role == "member"]) == 1
    assert subtasks[0].assignee == "New Assignee"
    assert subtasks[0].assignee_id == 5
    assert "Helper One" in subtasks[0].notes
    assert "Helper Two" in subtasks[0].notes


def test_owner_submit_rejects_invalid_selected_person_atomically():
    db = _make_session()
    _seed_project_team(db)

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(
                work_progress_draft=[
                    schemas.ProjectWorkProgressTaskDraft(
                        title="Invalid selected people task",
                        subtasks=[
                            schemas.ProjectWorkProgressSubTaskDraft(
                                title="Invalid key task",
                                assignee_id=9999,
                            )
                        ],
                    )
                ]
            ),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 422
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Task).filter_by(project_id=1).count() == 0
    assert db.query(models.ProjectMember).filter_by(project_id=1, role="member").count() == 1


def test_owner_submit_reuses_named_active_person_and_adds_project_member():
    db = _make_session()
    _seed_project_team(db)
    existing_assignee = models.Person(id=8, name="张三", system_role="normal_member", is_active=True)
    existing_helper = models.Person(id=9, name="李四", system_role="normal_member", is_active=True)
    db.add_all([existing_assignee, existing_helper])
    db.commit()

    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="导入人员关键任务",
                        assignee="张三",
                        helper="李四",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == existing_assignee.id
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [existing_helper.id]
    assert subtask.assignee_id == existing_assignee.id
    assert subtask.collaborator_ids == [existing_helper.id]
    assert {
        (member.person_id, member.role)
        for member in db.query(models.ProjectMember).filter_by(project_id=1, role="member")
    } >= {(existing_assignee.id, "member"), (existing_helper.id, "member")}


def test_owner_submit_creates_named_people_as_normal_members_without_accounts():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="新增导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="新增导入人员关键任务",
                        assignee="王五",
                        helper="赵六",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assignee = db.query(models.Person).filter_by(name="王五").one()
    helper = db.query(models.Person).filter_by(name="赵六").one()
    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert (assignee.is_active, assignee.system_role) == (True, "normal_member")
    assert (helper.is_active, helper.system_role) == (True, "normal_member")
    assert db.query(models.Account).filter(models.Account.person_id.in_([assignee.id, helper.id])).count() == 0
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == assignee.id
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [helper.id]
    assert subtask.assignee_id == assignee.id
    assert subtask.collaborator_ids == [helper.id]
    assert {
        (member.person_id, member.role)
        for member in db.query(models.ProjectMember).filter_by(project_id=1, role="member")
    } >= {(assignee.id, "member"), (helper.id, "member")}


@pytest.mark.parametrize("invalid_name", ["各项目经理", "咨询部", "mowasyadmin"])
def test_owner_submit_rejects_non_person_imported_assignee_without_creating_person(invalid_name):
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="无效导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="无效导入人员关键任务",
                        assignee=invalid_name,
                    )
                ],
            )
        ]
    )

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assert exc.value.status_code == 422
    assert db.query(models.Person).filter_by(name=invalid_name).count() == 0
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Task).filter_by(project_id=1).count() == 0


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
                        assignee_id=1,
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
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="Ready for review",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title="Coach review task",
                            assignee_id=1,
                        )
                    ],
                )
            ]
        ),
        current_user="owner",
        db=db,
    )

    with pytest.raises(HTTPException) as exc:
        approve_project(1, schemas.ProjectProfilePayload(), current_user="company_ceo", db=db)

    assert exc.value.status_code == 403
