from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers import projects


def test_add_member_sends_notification_using_project_name():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="Owner", system_role="normal_member", is_active=True),
            models.Person(id=2, name="New Member", system_role="normal_member", is_active=True),
            models.Account(username="moways", password_hash="x", person_id=1, status="active"),
            models.Project(id=1, name="Project", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
        ]
    )
    db.commit()

    result = projects.add_member(
        1,
        schemas.ProjectMemberPayload(person_id=2, role="member"),
        current_user="moways",
        db=db,
    )

    assert result["person_id"] == 2
    assert db.query(models.Notification).filter_by(type="project_member_added").count() == 1
