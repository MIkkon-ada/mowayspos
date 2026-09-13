from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api_errors import CodedHTTPException
from app.compatibility.project_roles import authorize_project_view, resolve_visible_project_ids
from app.database import Base
from app.domain.project_permissions import A_OWNER_SUBMIT, A_REVIEW_START, A_VIEW
from app.permissions import get_user_context_from_db
from app.services.project_access import authorize_project_action, resolve_member_project_ids


def _seed():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    people = [
        models.Person(id=1, name="Owner Coach", system_role="normal_member", is_active=True),
        models.Person(id=2, name="Legacy Owner", system_role="normal_member", is_active=True),
        models.Person(id=3, name="Company CEO", system_role="company_ceo", is_active=True),
    ]
    accounts = [
        models.Account(username="owner_coach", password_hash="x", person_id=1, status="active"),
        models.Account(username="legacy_owner", password_hash="x", person_id=2, status="active"),
        models.Account(username="company_ceo", password_hash="x", person_id=3, status="active"),
    ]
    project = models.Project(id=1, name="Access Project", status="active", is_active=True, owners="Legacy Owner")
    db.add_all(people + accounts + [project])
    db.add_all(
        [
            models.ProjectMember(project_id=1, person_id=1, role="owner"),
            models.ProjectMember(project_id=1, person_id=1, role="project_ceo"),
        ]
    )
    db.commit()
    return db, project


def test_authorize_project_action_builds_multi_role_subject():
    db, project = _seed()

    access = authorize_project_action("owner_coach", project, A_REVIEW_START, db)

    assert access.subject.project_roles == frozenset({"owner", "project_ceo"})
    assert access.role_source == "project_members"


def test_strict_write_action_does_not_use_legacy_owner():
    db, project = _seed()

    with pytest.raises(CodedHTTPException) as error:
        authorize_project_action("legacy_owner", project, A_OWNER_SUBMIT, db)

    assert error.value.code == "PROJECT_ACTION_DENIED"


def test_explicit_legacy_view_can_use_legacy_owner():
    db, project = _seed()

    access = authorize_project_view("legacy_owner", project, db)

    assert access.role_source == "legacy_fields"


def test_company_ceo_cannot_review_as_project_coach():
    db, project = _seed()

    with pytest.raises(CodedHTTPException) as error:
        authorize_project_action("company_ceo", project, A_REVIEW_START, db)

    assert error.value.status_code == 403
    assert error.value.code == "PROJECT_ACTION_DENIED"


def test_visible_project_ids_union_member_and_explicit_legacy_sources():
    db, project = _seed()
    context = get_user_context_from_db("legacy_owner", db)

    assert resolve_member_project_ids(context, db) == frozenset()
    assert resolve_visible_project_ids(context, db) == frozenset({project.id})
