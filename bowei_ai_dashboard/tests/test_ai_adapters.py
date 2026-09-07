from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from PIL import Image

from app import models
from app.ai.contracts import AIUpstreamError
from app.ai.adapters import OpenAICompatibleChatAdapter


def test_anthropic_json_mode_works_without_unsupported_assistant_prefill(monkeypatch):
    import anthropic
    from app.ai.adapters import DefaultAIAdapters

    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        assert kwargs["messages"][-1]["role"] == "user"
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"tasks": []}')])
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_kwargs: SimpleNamespace(messages=SimpleNamespace(create=create)))
    model = models.AIModel(provider="anthropic", model_name="claude-sonnet-4-6", base_url="https://example.test")

    text = DefaultAIAdapters().complete_chat(model, "secret", "extract JSON", timeout_seconds=30,
                                            response_format={"type": "json_object"})
    assert json.loads(text) == {"tasks": []}
    assert captured["model"] == "claude-sonnet-4-6"
    assert all(message["role"] == "user" for message in captured["messages"])
    assert "Return exactly one JSON object" in captured["messages"][0]["content"]
    assert "response_format" not in captured


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


@pytest.mark.parametrize("configured", [True, False])
def test_openai_compatible_chat_forwards_explicit_json_output(monkeypatch, configured):
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(openai, "OpenAI", lambda **_kwargs: fake_client)
    model = models.AIModel(
        code="deepseek-json",
        display_name="DeepSeek JSON",
        provider="deepseek",
        model_name="deepseek-chat",
        model_type="chat",
        base_url="https://example.test/v1",
        config_json=json.dumps({"response_format": {"type": "json_object"}} if configured else {}),
        enabled=True,
    )

    OpenAICompatibleChatAdapter().complete(
        model, "secret", "return JSON", timeout_seconds=30,
        **({} if configured else {"response_format": {"type": "json_object"}}),
    )

    assert captured["response_format"] == {"type": "json_object"}


def test_openai_compatible_chat_omits_json_output_without_configuration(monkeypatch):
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
        code="plain-chat",
        display_name="Plain Chat",
        provider="dashscope",
        model_name="qwen-plus",
        model_type="chat",
        base_url="https://example.test/v1",
        config_json="{}",
        enabled=True,
    )

    OpenAICompatibleChatAdapter().complete(model, "secret", "prompt", timeout_seconds=30)

    assert "response_format" not in captured


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


def test_deepseek_vision_sends_inline_png_data_without_remote_file_id(monkeypatch, tmp_path):
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: captured.update(client=kwargs) or fake_client)
    image_path = tmp_path / "sheet.png"
    Image.new("RGB", (8, 8), "white").save(image_path)
    model = models.AIModel(
        code="deepseek-vision",
        display_name="DeepSeek Vision",
        provider="deepseek",
        model_name="deepseek-v4-pro",
        model_type="chat",
        base_url="https://api.deepseek.com",
        config_json=json.dumps({"vision_workbook_analysis": True}),
        enabled=True,
    )

    result = OpenAICompatibleChatAdapter().complete_images(
        model, "secret", [image_path], "extract", timeout_seconds=30
    )

    assert result == "{}"
    assert captured["client"]["base_url"] == "https://api.deepseek.com/beta"
    image_part = captured["request"]["messages"][0]["content"][1]
    assert image_part["type"] == "file"
    assert image_part["file_data"].startswith("data:image/png;base64,")
    assert "file_id" not in image_part
