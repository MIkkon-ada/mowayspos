from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import meetings


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_draft_visibility_allows_creator_owner_and_ceo_but_not_member():
    db = _db()
    db.add_all([
        models.Person(id=1, name="Creator", is_active=True),
        models.Person(id=2, name="Owner", is_active=True),
        models.Person(id=3, name="Member", is_active=True),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=2, role="owner"),
        models.ProjectMember(project_id=1, person_id=3, role="member"),
    ])
    db.add_all([
        models.Account(username="creator", password_hash="x", person_id=1, status="active"),
        models.Account(username="owner", password_hash="x", person_id=2, status="active"),
        models.Account(username="member", password_hash="x", person_id=3, status="active"),
    ])
    db.commit()
    row = models.Meeting(project_id=1, creator_person_id=1, host="Creator", publish_status="draft")
    creator = {"name": "Creator", "is_ceo": False, "is_tech_admin": False}
    owner = {"name": "Owner", "is_ceo": False, "is_tech_admin": False}
    member = {"name": "Member", "is_ceo": False, "is_tech_admin": False}
    ceo = {"name": "CEO", "is_ceo": True, "is_tech_admin": False}

    assert meetings._can_view_meeting_draft(row, "creator", creator, db)
    assert meetings._can_view_meeting_draft(row, "owner", owner, db)
    assert meetings._can_view_meeting_draft(row, "ceo", ceo, db)
    assert not meetings._can_view_meeting_draft(row, "member", member, db)
