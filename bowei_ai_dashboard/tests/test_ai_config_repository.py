from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.repository import AIConfigurationRepository, InvalidAIModel, InvalidAIPolicy
from app.database import Base


TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="


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


def _chat_model(repo: AIConfigurationRepository):
    return repo.create_model(
        code="chat",
        display_name="chat",
        provider="deepseek",
        model_name="deepseek-chat",
        model_type="chat",
        base_url="https://api.deepseek.com",
        config={},
        enabled=True,
        source="custom",
    )


def test_policy_rejects_mismatched_model_type_and_duplicate_fallback(db):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    chat = _chat_model(repo)
    repo.replace_credential(chat.id, api_key="key", app_secret=None)

    with pytest.raises(InvalidAIPolicy, match="requires asr"):
        repo.save_policy(
            "speech.realtime",
            primary_model_id=chat.id,
            fallback_model_ids=[],
            timeout_seconds=30,
            max_attempts=1,
            enabled=True,
        )
    with pytest.raises(InvalidAIPolicy, match="duplicate"):
        repo.save_policy(
            "meeting.analysis",
            primary_model_id=chat.id,
            fallback_model_ids=[chat.id],
            timeout_seconds=30,
            max_attempts=2,
            enabled=True,
        )


@pytest.mark.parametrize(
    ("code", "model_type", "base_url"),
    [
        ("", "chat", "https://api.deepseek.com"),
        ("bad-type", "embedding", "https://api.deepseek.com"),
        ("bad-url", "chat", "ftp://api.deepseek.com"),
    ],
)
def test_model_rejects_invalid_identity_type_or_base_url(db, code, model_type, base_url):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)

    with pytest.raises(InvalidAIModel):
        repo.create_model(
            code=code,
            display_name="invalid",
            provider="deepseek",
            model_name="deepseek-chat",
            model_type=model_type,
            base_url=base_url,
            config={},
            enabled=True,
            source="custom",
        )


def test_credential_rotation_encrypts_secret_and_bumps_model_revision(db):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    chat = _chat_model(repo)

    credential = repo.replace_credential(chat.id, api_key="secret-key", app_secret=None)
    db.refresh(chat)

    assert credential.encrypted_api_key != "secret-key"
    assert repo.credential_configured(chat.id) is True
    assert chat.revision == 2


def test_enabled_policy_requires_a_credentialed_primary_model(db):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    chat = _chat_model(repo)

    with pytest.raises(InvalidAIPolicy, match="credential"):
        repo.save_policy(
            "meeting.analysis",
            primary_model_id=chat.id,
            fallback_model_ids=[],
            timeout_seconds=30,
            max_attempts=1,
            enabled=True,
        )

    policy = repo.save_policy(
        "meeting.analysis",
        primary_model_id=None,
        fallback_model_ids=[],
        timeout_seconds=30,
        max_attempts=1,
        enabled=False,
    )
    assert policy.enabled is False
    assert policy.primary_model_id is None


def test_policy_persists_fallback_timeout_seconds(db):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    chat = _chat_model(repo)
    repo.replace_credential(chat.id, api_key="key", app_secret=None)

    policy = repo.save_policy(
        "project.init.analysis",
        primary_model_id=chat.id,
        fallback_model_ids=[],
        timeout_seconds=200,
        fallback_timeout_seconds=25,
        max_attempts=1,
        enabled=True,
    )
    db.commit()
    db.expire_all()

    assert db.get(type(policy), policy.id).fallback_timeout_seconds == 25

    updated = repo.save_policy(
        "project.init.analysis",
        primary_model_id=chat.id,
        fallback_model_ids=[],
        timeout_seconds=200,
        fallback_timeout_seconds=26,
        max_attempts=1,
        enabled=True,
    )

    assert updated.policy_version == 2
