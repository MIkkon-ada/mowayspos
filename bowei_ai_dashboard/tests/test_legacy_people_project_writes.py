import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers import people


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="管理员", system_role="super_admin", is_active=True),
            models.Account(username="admin", password_hash="x", person_id=1, is_tech_admin=True, status="active"),
            models.Project(id=1, name="受保护项目", status="active", is_active=True),
        ]
    )
    db.commit()
    return db


@pytest.mark.parametrize("write_legacy_project", [
    lambda db: people.create_project(schemas.ProjectPayload(name="不得创建"), current_user="admin", db=db),
    lambda db: people.update_project(1, schemas.ProjectPayload(name="不得修改"), current_user="admin", db=db),
    lambda db: people.delete_project(1, current_user="admin", db=db),
])
def test_legacy_people_project_writes_are_retired(write_legacy_project):
    db = _db()

    with pytest.raises(HTTPException) as exc_info:
        write_legacy_project(db)

    assert exc_info.value.status_code == 410
    assert db.query(models.Project).filter_by(id=1, name="受保护项目", status="active", is_active=True).count() == 1
    assert db.query(models.Project).count() == 1
