from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api_errors import CodedHTTPException
from app.compatibility.project_roles import authorize_project_view, resolve_visible_project_ids
from app.database import Base
from app.domain.project_permissions import A_OWNER_SUBMIT, A_VIEW
from app.permissions import get_user_context_from_db
from app.services.project_access import authorize_project_action


def _seed():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    legacy_owner = models.Person(id=1, name="Legacy Owner", system_role="normal_member", is_active=True)
    account = models.Account(username="legacy_owner", password_hash="x", person_id=1, status="active")
    project = models.Project(id=1, name="Compatibility Project", status="active", is_active=True, owners="Legacy Owner")
    db.add_all([legacy_owner, account, project])
    db.commit()
    return db, project


def test_legacy_project_reads_are_owned_by_the_compatibility_boundary():
    db, project = _seed()

    access = authorize_project_view(
        "legacy_owner", project, db, denial_detail="permission denied — 仅项目成员可查看"
    )

    assert access.role_source == "legacy_fields"
    assert access.resource.project_id == project.id
    assert resolve_visible_project_ids(get_user_context_from_db("legacy_owner", db), db) == frozenset({project.id})
    with pytest.raises(CodedHTTPException) as error:
        authorize_project_action("legacy_owner", project, A_OWNER_SUBMIT, db)
    assert error.value.code == "PROJECT_ACTION_DENIED"


def test_legacy_switches_do_not_escape_compatibility_module():
    app_root = Path(__file__).resolve().parents[1] / "app"

    assert "allow_legacy" not in (app_root / "services" / "project_access.py").read_text(encoding="utf-8")
    assert "allow_legacy" not in (app_root / "routers" / "projects.py").read_text(encoding="utf-8")
    assert "allow_legacy" in (app_root / "compatibility" / "project_roles.py").read_text(encoding="utf-8")
