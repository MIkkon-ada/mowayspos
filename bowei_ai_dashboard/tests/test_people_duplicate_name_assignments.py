from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.people import _sync_person_assignments


@pytest.fixture
def duplicate_people_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    first = models.Person(id=1, name="重复姓名", is_active=True)
    second = models.Person(id=2, name="重复姓名", is_active=True)
    project = models.Project(id=1, name="成员身份项目", status="active", is_active=True, owners="重复姓名")
    db.add_all([first, second, project])
    db.flush()
    db.add_all(
        [
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="重复姓名", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="重复姓名", role="member"),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_assignment_sync_targets_person_id_without_rewriting_ambiguous_name_fields(duplicate_people_db):
    db = duplicate_people_db

    _sync_person_assignments(db, 2, "重复姓名", [], ["成员身份项目"], [])
    db.flush()

    memberships = db.query(models.ProjectMember).order_by(models.ProjectMember.person_id).all()
    project = db.get(models.Project, 1)
    assert [(row.person_id, row.role) for row in memberships] == [(1, "owner"), (2, "owner")]
    assert project.owners == "重复姓名"
