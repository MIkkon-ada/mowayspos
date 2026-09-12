import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import people


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Person(id=1, name="已登录用户", is_active=True),
            models.Person(id=2, name="目录成员", contact="sensitive-contact", is_active=True),
            models.Account(username="member", password_hash="x", person_id=1, status="active"),
        ]
    )
    db.commit()
    return db


@pytest.mark.parametrize("read_directory", [
    lambda db: people.list_people(current_user="", db=db),
    lambda db: people.get_person(2, current_user="", db=db),
])
def test_people_directory_requires_an_authenticated_account(read_directory):
    with pytest.raises(HTTPException) as exc_info:
        read_directory(_db())

    assert exc_info.value.status_code == 401


def test_authenticated_account_can_read_people_directory():
    db = _db()

    assert [row["id"] for row in people.list_people(current_user="member", db=db)] == [1, 2]
    assert people.get_person(2, current_user="member", db=db)["contact"] == "sensitive-contact"
