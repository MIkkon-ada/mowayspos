from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.main import _auth_me_projects
from app.permissions import get_user_context_from_db
from app.routers import projects


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    ceo = models.Account(username="company_ceo", password_hash="x", person_id=1, status="active")
    owner = models.Account(username="owner", password_hash="x", person_id=2, status="active")
    db.add_all(
        [
            models.Person(id=1, name="Company CEO", system_role="company_ceo", is_active=True),
            models.Person(id=2, name="Owner", system_role="normal_member", is_active=True),
            ceo,
            owner,
            models.Project(id=1, name="Draft", status="draft"),
            models.Project(id=2, name="Dispatched", status="dispatched"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=2, person_id=2, person_name_snapshot="Owner", role="owner"),
        ]
    )
    db.commit()
    return db, ceo, owner


def test_owner_project_list_excludes_drafts_but_ceo_can_manage_them():
    db, ceo, owner = _db()

    owner_projects = projects.list_projects(current_user=owner.username, db=db)
    ceo_projects = projects.list_projects(current_user=ceo.username, db=db)

    assert [project["id"] for project in owner_projects] == [2]
    assert [project["id"] for project in ceo_projects] == [1, 2]


def test_auth_me_projects_excludes_drafts_for_owner_but_not_ceo():
    db, ceo, owner = _db()
    owner_context = get_user_context_from_db(owner.username, db)
    ceo_context = get_user_context_from_db(ceo.username, db)

    owner_projects = _auth_me_projects(owner, owner_context, db)
    ceo_projects = _auth_me_projects(ceo, ceo_context, db)

    assert [project["id"] for project in owner_projects] == [2]
    assert [project["id"] for project in ceo_projects] == [1, 2]
