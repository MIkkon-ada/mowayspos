from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai.contracts import AIUpstreamError, Capability
from app.ai.repository import AIConfigurationRepository
from app.ai.service import AIService
from app.database import Base


TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="


class FailingAdapters:
    def complete_chat(self, _model, _api_key, _prompt, *, timeout_seconds):
        raise AIUpstreamError(
            "AI_UPSTREAM_5XX", retryable=True, message="upstream do-not-log-me"
        )


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


def test_logs_never_contain_prompt_secret_or_raw_exception_text(db):
    secret = "do-not-log-me"
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    model = repo.create_model(
        code="primary",
        display_name="Primary",
        provider="deepseek",
        model_name="deepseek-chat",
        model_type="chat",
        base_url="https://api.deepseek.com",
        config={},
        enabled=True,
        source="custom",
    )
    repo.replace_credential(model.id, api_key=secret, app_secret=None)
    repo.save_policy(
        Capability.MEETING_ANALYSIS,
        primary_model_id=model.id,
        fallback_model_ids=[],
        timeout_seconds=30,
        max_attempts=1,
        enabled=True,
    )

    with pytest.raises(AIUpstreamError):
        AIService(db, adapters=FailingAdapters(), cipher_key=TEST_FERNET_KEY).invoke_chat(
            Capability.MEETING_ANALYSIS, f"prompt {secret}"
        )

    logs = db.query(models.AIInvocationLog).all()
    assert len(logs) == 1
    assert secret not in repr(logs)
    assert logs[0].error_code == "AI_UPSTREAM_5XX"
