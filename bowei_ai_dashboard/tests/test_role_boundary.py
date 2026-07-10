from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.main import _public_project_roles
from app.permissions import can_ceo_decide_by_project
from app.services.notify import project_coach_person_ids
from app.services.policy import role_allows_batch, user_roles_in_project


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_people_and_projects(db):
    company_ceo = models.Person(id=1, name="Company CEO", system_role="company_ceo", is_active=True)
    project_ceo_current = models.Person(id=2, name="Project Coach A", system_role="normal_member", is_active=True)
    project_ceo_other = models.Person(id=3, name="Project Coach B", system_role="company_ceo", is_active=True)
    db.add_all(
        [
            company_ceo,
            project_ceo_current,
            project_ceo_other,
            models.Project(id=1, name="Project A", status="active"),
            models.Project(id=2, name="Project B", status="active"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Project Coach A", role="project_ceo"),
            models.ProjectMember(project_id=2, person_id=3, person_name_snapshot="Project Coach B", role="project_ceo"),
        ]
    )
    db.commit()
    return company_ceo, project_ceo_current, project_ceo_other


def test_public_project_roles_do_not_inject_project_ceo_for_company_ceo():
    assert _public_project_roles(["owner"], is_ceo=True) == ["project_owner"]


def test_user_roles_in_project_does_not_promote_company_ceo_to_project_ceo():
    db = _make_session()
    company_ceo, _, _ = _seed_people_and_projects(db)

    roles = user_roles_in_project(
        {"person_id": company_ceo.id, "is_ceo": True, "is_tech_admin": False},
        1,
        db,
    )

    assert roles == set()


def test_company_ceo_can_still_view_batch_without_project_ceo_role():
    db = _make_session()
    company_ceo, _, _ = _seed_people_and_projects(db)

    assert role_allows_batch(
        {"person_id": company_ceo.id, "name": "Company CEO", "can_view_all": True, "is_ceo": True, "is_tech_admin": False},
        submitter="someone_else",
        project_id=1,
        raw_status="待确认",
        cache={},
    )


def test_can_ceo_decide_by_project_requires_real_project_ceo():
    db = _make_session()
    company_ceo, _, _ = _seed_people_and_projects(db)

    assert not can_ceo_decide_by_project(
        {"person_id": company_ceo.id, "is_ceo": True, "is_tech_admin": False, "can_confirm_all": True},
        1,
        db,
    )


def test_super_admin_can_still_decide_globally():
    db = _make_session()
    _seed_people_and_projects(db)

    assert can_ceo_decide_by_project(
        {"person_id": None, "is_ceo": False, "is_tech_admin": True, "can_confirm_all": True},
        1,
        db,
    )


def test_project_coach_person_ids_only_returns_current_project_project_ceo():
    db = _make_session()
    _, project_ceo_current, project_ceo_other = _seed_people_and_projects(db)

    assert project_coach_person_ids(1, db) == [project_ceo_current.id]
    assert project_coach_person_ids(2, db) == [project_ceo_other.id]
