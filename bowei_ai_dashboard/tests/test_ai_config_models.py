from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.schemas import AIPolicyWrite


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_ai_models_enforce_unique_stable_code(db):
    db.add(
        models.AIModel(
            code="deepseek-chat-primary",
            display_name="DeepSeek",
            provider="deepseek",
            model_name="deepseek-chat",
            model_type="chat",
            enabled=True,
            source="custom",
        )
    )
    db.commit()
    db.add(
        models.AIModel(
            code="deepseek-chat-primary",
            display_name="Duplicate",
            provider="deepseek",
            model_name="deepseek-chat",
            model_type="chat",
            enabled=True,
            source="custom",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_ai_policy_is_unique_per_capability_and_log_has_no_payload_columns(db):
    db.add(
        models.AICapabilityPolicy(
            capability_key="meeting.analysis", enabled=False, policy_version=1
        )
    )
    db.commit()

    db.add(
        models.AICapabilityPolicy(
            capability_key="meeting.analysis", enabled=False, policy_version=1
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()

    assert inspect(db.bind).has_table("ai_invocation_logs")
    fields = {column.name for column in models.AIInvocationLog.__table__.columns}
    assert {"prompt", "raw_response", "audio", "api_key"}.isdisjoint(fields)


def test_ai_policy_fallback_timeout_defaults_to_25_in_model_and_schema(db):
    policy = models.AICapabilityPolicy(capability_key="meeting.analysis")
    db.add(policy)
    db.flush()

    payload = AIPolicyWrite(
        primary_model_id=None,
        fallback_model_ids=[],
        timeout_seconds=30,
        max_attempts=1,
        enabled=False,
    )

    assert policy.fallback_timeout_seconds == 25
    assert payload.fallback_timeout_seconds == 25
