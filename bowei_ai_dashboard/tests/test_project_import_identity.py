from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.projects import _active_person_by_unique_name, _person_id_for_name
from app.services.notify import person_id_for_name


@pytest.fixture
def project_import_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="重复姓名", is_active=True),
            models.Person(id=2, name="重复姓名", is_active=True),
            models.Person(id=3, name="唯一姓名", is_active=True),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_project_import_resolves_only_unique_active_person_name(project_import_identity_db):
    person = _active_person_by_unique_name(project_import_identity_db, "唯一姓名", "负责人")

    assert person.id == 3


def test_project_import_rejects_ambiguous_active_person_name(project_import_identity_db):
    with pytest.raises(HTTPException) as exc:
        _active_person_by_unique_name(project_import_identity_db, "重复姓名", "负责人")

    assert exc.value.status_code == 422


def test_project_import_returns_none_for_unknown_person_name(project_import_identity_db):
    assert _active_person_by_unique_name(project_import_identity_db, "尚未建档", "负责人") is None


def test_project_owner_name_bridge_does_not_choose_first_duplicate(project_import_identity_db):
    db = project_import_identity_db

    assert _person_id_for_name("重复姓名", db) is None
    assert _person_id_for_name("唯一姓名", db) == 3
    assert person_id_for_name("重复姓名", db) is None
    assert person_id_for_name("唯一姓名", db) == 3
