from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.compatibility.project_roles import resolve_project_roles
from app.database import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_project(*, owner_active: bool = True, legacy_owner: str = "Legacy Owner"):
    db = _make_session()
    owner = models.Person(id=1, name="Legacy Owner", system_role="normal_member", is_active=owner_active)
    member = models.Person(id=2, name="Member", system_role="normal_member", is_active=True)
    project = models.Project(
        id=1,
        name="Compatibility Project",
        status="active",
        is_active=True,
        owners=legacy_owner,
    )
    db.add_all([owner, member, project])
    db.commit()
    return db, project, owner, member


def test_project_members_are_authoritative():
    db, project, owner, _ = _seed_project()
    db.add(models.ProjectMember(project_id=project.id, person_id=owner.id, role="owner"))
    project.collaborators = "Legacy Owner"
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset({"owner"})
    assert resolution.source == "project_members"


def test_legacy_fields_are_disabled_by_default():
    db, project, owner, _ = _seed_project()

    resolution = resolve_project_roles(db, owner.id, project.id)

    assert resolution.roles == frozenset()
    assert resolution.source == "none"


def test_legacy_fields_are_used_only_when_explicit_and_current_person_has_no_valid_roles():
    db, project, owner, _ = _seed_project()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset({"owner"})
    assert resolution.source == "legacy_fields"


def test_current_person_member_rows_disable_legacy_grants_for_that_person():
    db, project, owner, _ = _seed_project()
    db.add(models.ProjectMember(project_id=project.id, person_id=owner.id, role="member"))
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset({"member"})
    assert resolution.source == "project_members"


def test_other_people_member_rows_do_not_disable_explicit_legacy_read_fallback():
    db, project, owner, member = _seed_project()
    db.add(models.ProjectMember(project_id=project.id, person_id=member.id, role="member"))
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset({"owner"})
    assert resolution.source == "legacy_fields"


def test_legacy_parser_supports_all_supported_separators_and_multiple_roles():
    db, project, owner, _ = _seed_project(legacy_owner="Legacy Owner,Other")
    project.coordinator = "Legacy Owner；Other"
    project.collaborators = "Other/Legacy Owner\nThird"
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset({"owner", "coordinator", "member"})


def test_unknown_legacy_names_and_roles_do_not_grant_access():
    db, project, owner, _ = _seed_project(legacy_owner="Unknown Person")
    project.coordinator = "Unknown Person"
    project.collaborators = "Unknown Person"
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset()
    assert resolution.source == "none"


def test_inactive_people_do_not_receive_legacy_roles():
    db, project, owner, _ = _seed_project(owner_active=False)

    resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)

    assert resolution.roles == frozenset()
    assert resolution.source == "none"


def test_multiple_project_member_rows_are_returned_as_all_roles():
    db, project, owner, _ = _seed_project()
    db.add_all(
        [
            models.ProjectMember(project_id=project.id, person_id=owner.id, role="owner"),
            models.ProjectMember(project_id=project.id, person_id=owner.id, role="project_ceo"),
        ]
    )
    db.commit()

    resolution = resolve_project_roles(db, owner.id, project.id)

    assert resolution.roles == frozenset({"owner", "project_ceo"})
