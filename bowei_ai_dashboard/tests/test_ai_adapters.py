from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app import models
from app.ai.contracts import AIUpstreamError
from app.ai.adapters import OpenAICompatibleChatAdapter


def test_openai_compatible_chat_uses_model_max_output_tokens(monkeypatch):
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(openai, "OpenAI", lambda **_kwargs: fake_client)
    model = models.AIModel(
        code="chat",
        display_name="Chat",
        provider="deepseek",
        model_name="deepseek-chat",
        model_type="chat",
        base_url="https://example.test/v1",
        config_json=json.dumps({"max_output_tokens": 8192}),
        enabled=True,
    )

    result = OpenAICompatibleChatAdapter().complete(
        model, "secret", "prompt", timeout_seconds=30
    )

    assert result == "OK"
    assert captured["max_tokens"] == 8192


def test_openai_timeout_is_mapped_and_sdk_retries_are_disabled(monkeypatch):
    captured: dict = {}

    class FakeCompletions:
        def create(self, **_kwargs):
            raise openai.APITimeoutError(
                request=httpx.Request("POST", "https://example.test/v1/chat/completions")
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda **kwargs: captured.update(kwargs) or fake_client,
    )
    model = models.AIModel(
        code="chat",
        display_name="Chat",
        provider="dashscope",
        model_name="qwen-plus",
        model_type="chat",
        base_url="https://example.test/v1",
        config_json="{}",
        enabled=True,
    )

    with pytest.raises(AIUpstreamError) as error:
        OpenAICompatibleChatAdapter().complete(
            model, "secret", "prompt", timeout_seconds=60
        )

    assert error.value.code == "AI_UPSTREAM_TIMEOUT"
    assert error.value.retryable is True
    assert captured["max_retries"] == 0
