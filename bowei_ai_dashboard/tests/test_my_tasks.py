from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_person(db, person_id: int, name: str, *, active: bool = True):
    person = models.Person(
        id=person_id,
        name=name,
        system_role="normal_member",
        is_active=active,
    )
    db.add(person)
    return person


def _add_project(db, project_id: int, status: str, person_ids: list[int]):
    project = models.Project(
        id=project_id,
        name=f"Project {project_id}",
        status=status,
        is_active=status == "active",
    )
    db.add(project)
    for person_id in person_ids:
        db.add(models.ProjectMember(
            project_id=project_id,
            person_id=person_id,
            person_name_snapshot=f"Person {person_id}",
            role="member",
        ))
    return project


def _add_task(db, project_id: int, task_id: int, owner_name: str,
              owner_id: int | None, *, deleted: bool = False):
    task = models.Task(
        id=task_id,
        project_id=project_id,
        key_task=f"Workstream {task_id}",
        is_deleted=deleted,
    )
    db.add(task)
    db.flush()
    db.add(models.SubTask(
        id=task_id,
        task_id=task_id,
        title=f"Key task {task_id}",
        assignee=owner_name,
        assignee_id=owner_id,
    ))


def _account(db, username: str, person_id: int | None):
    db.add(models.Account(
        username=username,
        password_hash="test-only",
        person_id=person_id,
        status="active",
    ))


def test_my_tasks_separates_people_with_the_same_display_name():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "同名人员")
    _add_person(db, 2, "同名人员")
    _account(db, "first", 1)
    _account(db, "second", 2)
    _add_project(db, 10, "active", [1, 2])
    _add_task(db, 10, 100, "同名人员", 1)
    _add_task(db, 10, 101, "同名人员", 2)
    db.commit()

    first_result = list_my_tasks("first", db)
    second_result = list_my_tasks("second", db)

    assert [row["id"] for row in first_result["tasks"]] == [100]
    assert [row["id"] for row in second_result["tasks"]] == [101]


def test_my_tasks_keeps_id_bound_task_after_person_rename():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "更新后的姓名")
    _account(db, "owner", 1)
    _add_project(db, 10, "active", [1])
    _add_task(db, 10, 100, "历史姓名", 1)
    db.commit()

    result = list_my_tasks("owner", db)

    assert [row["id"] for row in result["tasks"]] == [100]


def test_person_rename_endpoint_keeps_id_bound_task_in_my_tasks(monkeypatch):
    from app import schemas
    from app.routers import people as people_router
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "旧姓名")
    _account(db, "owner", 1)
    _add_project(db, 10, "active", [1])
    _add_task(db, 10, 100, "旧姓名", 1)
    db.query(models.ProjectMember).filter_by(project_id=10, person_id=1).one().person_name_snapshot = "旧姓名"
    db.commit()
    monkeypatch.setattr(people_router, "_require_admin", lambda _user, _db: None)

    people_router.update_person(
        1,
        schemas.PersonPayload(name="新姓名"),
        current_user="admin",
        db=db,
    )

    result = list_my_tasks("owner", db)
    member = db.query(models.ProjectMember).filter_by(project_id=10, person_id=1).one()
    assert [row["id"] for row in result["tasks"]] == [100]
    assert result["tasks"][0]["assignee_id"] == 1
    assert member.person_name_snapshot == "新姓名"


def test_my_tasks_uses_legacy_name_only_when_it_uniquely_maps_to_caller():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "唯一人员")
    _account(db, "owner", 1)
    _add_project(db, 10, "active", [1])
    _add_task(db, 10, 100, "唯一人员", None)
    db.commit()

    result = list_my_tasks("owner", db)

    assert [row["id"] for row in result["tasks"]] == [100]
    assert result["ambiguous_assignment_count"] == 0


def test_my_tasks_does_not_guess_between_ambiguous_legacy_names():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "重名人员甲")
    _add_person(db, 2, "重名人员甲")
    _account(db, "first", 1)
    _add_project(db, 10, "active", [1, 2])
    _add_task(db, 10, 100, "重名人员甲", None)
    db.commit()

    result = list_my_tasks("first", db)

    assert result["tasks"] == []
    assert result["ambiguous_assignment_count"] == 1


def test_my_tasks_is_limited_to_visible_active_scope_projects():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "负责人")
    _account(db, "owner", 1)
    _add_project(db, 10, "active", [1])
    _add_project(db, 11, "active", [])
    _add_project(db, 12, "archived", [1])
    _add_task(db, 10, 100, "负责人", 1)
    _add_task(db, 11, 101, "负责人", 1)
    _add_task(db, 12, 102, "负责人", 1)
    db.commit()

    result = list_my_tasks("owner", db)

    assert [project["id"] for project in result["projects"]] == [10]
    assert [row["id"] for row in result["tasks"]] == [100]


@pytest.mark.parametrize(
    "status",
    ["draft", "dispatched", "pending_review", "returned", "pending_close", "ended", "archived"],
)
def test_my_tasks_excludes_projects_outside_personal_task_lifecycle(status: str):
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "负责人")
    _account(db, "owner", 1)
    _add_project(db, 10, status, [1])
    _add_task(db, 10, 100, "负责人", 1)
    db.commit()

    result = list_my_tasks("owner", db)

    assert result["projects"] == []
    assert result["tasks"] == []


def test_my_tasks_accepts_legacy_pending_kickoff_scope():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _add_person(db, 1, "负责人")
    _account(db, "owner", 1)
    _add_project(db, 10, "pending_kickoff", [1])
    _add_task(db, 10, 100, "负责人", 1)
    db.commit()

    result = list_my_tasks("owner", db)

    assert [project["id"] for project in result["projects"]] == [10]
    assert [row["id"] for row in result["tasks"]] == [100]


def test_my_tasks_requires_an_active_account_with_stable_person_binding():
    from app.services.my_tasks import list_my_tasks

    db = _db()
    _account(db, "unlinked", None)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        list_my_tasks("unlinked", db)

    assert exc_info.value.status_code == 409


def test_my_tasks_route_uses_login_account_and_accepts_no_identity_override():
    import inspect

    from app.routers.subtasks import get_my_tasks

    db = _db()
    _add_person(db, 1, "本人")
    _account(db, "owner", 1)
    _add_project(db, 10, "active", [1])
    _add_task(db, 10, 100, "本人", 1)
    db.commit()

    result = get_my_tasks(current_user="owner", db=db)

    assert [row["id"] for row in result["tasks"]] == [100]
    assert "person_id" not in inspect.signature(get_my_tasks).parameters
    assert "assignee" not in inspect.signature(get_my_tasks).parameters
