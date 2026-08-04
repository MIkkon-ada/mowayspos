from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import meetings


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_action_items_without_source_or_acceptance_are_explicitly_flagged():
    db = _db()
    item = meetings._tag_action_item_members(
        [{"member": "Unknown", "task": "Review scope", "deadline": ""}],
        project_id=None,
        db=db,
    )[0]

    assert item["member"] == "待确认"
    assert item["deadline"] == "待确认"
    assert item["acceptance_criteria"] == "待确认"
    assert item["evidence_quote"] == "待确认"


def test_action_items_keep_explicit_source_and_completion_fields():
    db = _db()
    item = meetings._tag_action_item_members(
        [{
            "member": "Owner",
            "task": "Review scope",
            "deadline": "Friday",
            "acceptance_criteria": "Scope approved",
            "evidence_quote": "Owner: I will review scope by Friday.",
        }],
        project_id=None,
        db=db,
    )[0]

    assert item["deadline"] == "Friday"
    assert item["acceptance_criteria"] == "Scope approved"
    assert item["evidence_quote"] == "Owner: I will review scope by Friday."

