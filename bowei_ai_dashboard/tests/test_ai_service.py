from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai.contracts import AICapabilityNotConfigured, AIInvocationContext, AIUpstreamError, Capability
from app.ai.repository import AIConfigurationRepository
from app.ai.service import AIService
from app.database import Base


TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="


class FakeAdapters:
    def __init__(self):
        self.chat_errors = {}
        self.chat_results = {}
        self.chat_calls = []
        self.chat_timeouts = []
        self.vision_results = {}
        self.vision_calls = []
        self.vision_timeouts = []

    def complete_chat(self, model, api_key, prompt, *, timeout_seconds):
        self.chat_calls.append(model.id)
        self.chat_timeouts.append(timeout_seconds)
        if model.id in self.chat_errors:
            raise self.chat_errors[model.id]
        return self.chat_results[model.id]

    def complete_project_init_vision(self, model, api_key, images, prompt, *, timeout_seconds):
        self.vision_calls.append((model.id, list(images)))
        self.vision_timeouts.append(timeout_seconds)
        return self.vision_results[model.id]


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


@pytest.fixture()
def configured_chat_policy(db):
    repo = AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY)
    primary = repo.create_model(
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
    fallback = repo.create_model(
        code="fallback",
        display_name="Fallback",
        provider="dashscope",
        model_name="qwen-plus",
        model_type="chat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        config={},
        enabled=True,
        source="custom",
    )
    repo.replace_credential(primary.id, api_key="primary-key", app_secret=None)
    repo.replace_credential(fallback.id, api_key="fallback-key", app_secret=None)
    repo.save_policy(
        Capability.MEETING_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=30,
        max_attempts=2,
        enabled=True,
    )
    return primary, fallback


@pytest.fixture()
def fake_adapters():
    return FakeAdapters()


@pytest.mark.parametrize(
    "code",
    [
        "AI_UPSTREAM_TIMEOUT",
        "AI_UPSTREAM_CONNECTION",
        "AI_UPSTREAM_RATE_LIMIT",
        "AI_UPSTREAM_5XX",
    ],
)
def test_chat_uses_primary_then_retryable_fallback_and_logs_each_attempt(
    db, configured_chat_policy, fake_adapters, code
):
    primary, fallback = configured_chat_policy
    fake_adapters.chat_errors[primary.id] = AIUpstreamError(
        code, retryable=True
    )
    fake_adapters.chat_results[fallback.id] = '{"title":"ok"}'

    result = AIService(
        db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY
    ).invoke_chat(
        Capability.MEETING_ANALYSIS,
        "prompt",
        AIInvocationContext(actor="pm", resource_type="meeting", resource_id=8),
    )

    assert result.text == '{"title":"ok"}'
    assert result.model_code == "fallback"
    logs = db.query(models.AIInvocationLog).order_by(models.AIInvocationLog.attempt_no).all()
    assert [(row.status, row.error_code, row.fallback_used) for row in logs] == [
        ("failed", code, False),
        ("succeeded", "", True),
    ]
    assert [(row.actor, row.resource_type, row.resource_id) for row in logs] == [
        ("pm", "meeting", 8),
        ("pm", "meeting", 8),
    ]


@pytest.mark.parametrize("code", ["AI_UPSTREAM_AUTH", "AI_UPSTREAM_BAD_REQUEST"])
def test_non_retryable_error_does_not_try_fallback(db, configured_chat_policy, fake_adapters, code):
    primary, _fallback = configured_chat_policy
    fake_adapters.chat_errors[primary.id] = AIUpstreamError(
        code, retryable=False
    )

    with pytest.raises(AIUpstreamError, match="AI upstream request failed"):
        AIService(db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY).invoke_chat(
            Capability.MEETING_ANALYSIS, "prompt"
        )

    assert fake_adapters.chat_calls == [primary.id]


def test_task_plan_drafting_has_no_client_request_timeout(db, configured_chat_policy, fake_adapters):
    primary, _fallback = configured_chat_policy
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.TASK_PLAN_PROPOSAL,
        primary_model_id=primary.id,
        fallback_model_ids=[],
        timeout_seconds=30,
        max_attempts=1,
        enabled=True,
    )
    fake_adapters.chat_results[primary.id] = '{"plans":[]}'

    AIService(db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY).invoke_chat(
        Capability.TASK_PLAN_PROPOSAL, "draft plans"
    )

    assert fake_adapters.chat_timeouts == [None]


def test_project_init_analysis_uses_primary_and_fallback_timeouts_after_retryable_failure(
    db, configured_chat_policy, fake_adapters
):
    primary, fallback = configured_chat_policy
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=200,
        fallback_timeout_seconds=25,
        max_attempts=2,
        enabled=True,
    )
    fake_adapters.chat_errors[primary.id] = AIUpstreamError(
        "AI_UPSTREAM_TIMEOUT", retryable=True
    )
    fake_adapters.chat_results[fallback.id] = '{"tasks":[]}'

    AIService(db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY).invoke_chat(
        Capability.PROJECT_INIT_ANALYSIS, "extract"
    )

    assert fake_adapters.chat_timeouts == [200, 25]


def test_project_init_vision_uses_only_explicitly_opted_in_model(
    db, configured_chat_policy, fake_adapters, tmp_path
):
    primary, fallback = configured_chat_policy
    primary.config_json = '{"vision_workbook_analysis":true}'
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=30,
        max_attempts=2,
        enabled=True,
    )
    db.commit()
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"png")
    fake_adapters.vision_results[primary.id] = '{"tasks":[]}'

    result = AIService(
        db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY
    ).invoke_project_init_vision(
        [image_path], "extract", AIInvocationContext(resource_type="project_init", resource_id=8)
    )

    assert result.text == '{"tasks":[]}'
    assert result.model_code == "primary"
    assert fake_adapters.vision_calls == [(primary.id, [image_path])]
    assert fallback.id not in [model_id for model_id, _ in fake_adapters.vision_calls]


def test_project_init_vision_uses_fallback_timeout_when_primary_is_not_vision_eligible(
    db, configured_chat_policy, fake_adapters, tmp_path
):
    primary, fallback = configured_chat_policy
    fallback.provider = "deepseek"
    fallback.config_json = '{"vision_project_init_analysis":true}'
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=200,
        fallback_timeout_seconds=25,
        max_attempts=2,
        enabled=True,
    )
    db.commit()
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"png")
    fake_adapters.vision_results[fallback.id] = '{"tasks":[]}'

    result = AIService(
        db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY
    ).invoke_project_init_vision([image_path], "extract")

    assert result.model_code == "fallback"
    assert fake_adapters.vision_timeouts == [25]


def test_project_init_vision_accepts_the_generic_project_init_opt_in(
    db, configured_chat_policy, fake_adapters, tmp_path
):
    primary, _fallback = configured_chat_policy
    primary.config_json = '{"vision_project_init_analysis":true}'
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[],
        timeout_seconds=30,
        max_attempts=1,
        enabled=True,
    )
    db.commit()
    image_path = tmp_path / "scanned-page.png"
    image_path.write_bytes(b"png")
    fake_adapters.vision_results[primary.id] = '{"tasks":[]}'

    result = AIService(
        db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY
    ).invoke_project_init_vision([image_path], "extract")

    assert result.model_code == "primary"
    assert fake_adapters.vision_calls == [(primary.id, [image_path])]


def test_project_init_vision_rejects_models_without_explicit_opt_in(
    db, configured_chat_policy, fake_adapters, tmp_path
):
    primary, fallback = configured_chat_policy
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=30,
        max_attempts=2,
        enabled=True,
    )
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"png")

    with pytest.raises(AICapabilityNotConfigured, match="vision"):
        AIService(
            db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY
        ).invoke_project_init_vision([image_path], "extract")

    assert fake_adapters.vision_calls == []
