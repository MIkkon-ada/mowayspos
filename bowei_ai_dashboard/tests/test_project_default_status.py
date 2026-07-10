from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models


def test_project_default_status_and_active_flag_are_safe() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    db = SessionLocal()
    try:
        project = models.Project(name="New Project")
        db.add(project)
        db.flush()
        db.refresh(project)

        assert project.status == "draft"
        assert project.is_active is False
    finally:
        db.rollback()
        db.close()
