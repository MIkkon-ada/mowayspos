from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import people


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_legacy_people_projects_list_is_read_only_on_empty_database():
    db = _db()

    assert people.list_projects(current_user="owner", db=db) == []
    assert db.query(models.Project).count() == 0


def test_legacy_people_projects_list_uses_current_project_visibility():
    db = _db()
    db.add_all(
        [
            models.Person(id=1, name="项目成员", system_role="normal_member", is_active=True),
            models.Person(id=2, name="项目外人员", system_role="normal_member", is_active=True),
            models.Account(username="member", password_hash="x", person_id=1, status="active"),
            models.Account(username="outsider", password_hash="x", person_id=2, status="active"),
            models.Project(id=1, name="可见项目", status="active", is_active=True),
            models.Project(id=2, name="不可见项目", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="项目成员", role="member"),
        ]
    )
    db.commit()

    assert [project["id"] for project in people.list_projects(current_user="member", db=db)] == [1]
    assert people.list_projects(current_user="outsider", db=db) == []
