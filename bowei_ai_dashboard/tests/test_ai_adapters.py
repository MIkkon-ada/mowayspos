from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from app import models
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
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_kwargs: fake_client))
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
