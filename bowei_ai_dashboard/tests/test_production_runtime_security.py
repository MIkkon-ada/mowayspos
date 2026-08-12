from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import llm_config as llm_store
from app import settings as runtime_settings
from app.routers import llm_config as llm_router
from app.routers import transcribe


class _TrackingCookies(dict):
    def __init__(self):
        super().__init__({"custom_ws_session": "session-id"})
        self.requested: list[str] = []

    def get(self, key, default=None):
        self.requested.append(key)
        return super().get(key, default)


class _RejectingWebSocket:
    def __init__(self):
        self.cookies = _TrackingCookies()
        self.closed: tuple[int, str] | None = None
        self._sent: list[dict] = []

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        self._sent.append(data)

    async def close(self, *, code: int, reason: str = ""):
        self.closed = (code, reason)


class _RouteWebSocket(_RejectingWebSocket):
    async def close(self, *, code: int = 1000, reason: str = ""):
        self.closed = (code, reason)


def test_websocket_auth_uses_the_runtime_http_session_cookie_name(monkeypatch):
    websocket = _RejectingWebSocket()
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda session_id: None)

    asyncio.run(transcribe.transcribe_stream(websocket, db=object()))

    assert websocket.cookies.requested == ["custom_ws_session"]
    assert websocket.closed is not None
    assert websocket.closed[0] == 4001


def test_websocket_reports_missing_dashscope_key(monkeypatch):
    websocket = _RouteWebSocket()
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    monkeypatch.setattr(
        transcribe,
        "get_provider_config",
        lambda _provider: {"api_key": ""},
    )

    asyncio.run(transcribe.transcribe_stream(websocket, db=object()))

    assert websocket._sent == [{
        "type": "error",
        "code": "ASR_NOT_CONFIGURED",
        "message": "未配置语音识别服务，请联系管理员",
        "retryable": False,
    }]
    assert websocket.closed == (4002, "")


def test_websocket_passes_authenticated_user_key_and_db_to_coordinator(monkeypatch):
    websocket = _RouteWebSocket()
    fake_db = object()
    received: dict = {}

    async def coordinator(_websocket, **kwargs):
        received.update(kwargs)

    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    monkeypatch.setattr(
        transcribe,
        "get_provider_config",
        lambda _provider: {"api_key": "runtime-key"},
    )
    monkeypatch.setattr(transcribe, "run_transcribe_stream", coordinator)

    asyncio.run(transcribe.transcribe_stream(websocket, db=fake_db))

    assert received == {
        "current_user": "member",
        "db": fake_db,
        "api_key": "runtime-key",
    }
    assert websocket.closed == (1000, "")


def test_production_rejects_api_keys_from_the_settings_endpoint(monkeypatch):
    secret = "never-persist-or-return-this-key"
    saved: list[dict] = []
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(llm_router, "load_configs", lambda: {})
    monkeypatch.setattr(llm_router, "save_configs", saved.append)

    with pytest.raises(HTTPException) as caught:
        llm_router.save_config("deepseek", llm_router.LLMConfigPayload(api_key=secret, base_url="https://api.deepseek.com", model="deepseek-chat", enabled=True), current_user="admin", db=object())

    assert caught.value.status_code == 400
    assert "环境变量" in caught.value.detail
    assert saved == []
    assert secret not in repr(caught.value)


def test_production_can_persist_non_secret_provider_settings(monkeypatch):
    saved: list[dict] = []
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(
        llm_router,
        "load_configs",
        lambda: {
            "anthropic": {"api_key": "other-legacy-secret", "enabled": True},
            "deepseek": {"api_key": "legacy-file-secret", "enabled": False},
        },
    )
    monkeypatch.setattr(llm_router, "save_configs", saved.append)

    result = llm_router.save_config(
        "deepseek",
        llm_router.LLMConfigPayload(
            api_key="***",
            base_url="https://gateway.example.invalid/v1",
            model="deepseek-chat",
            enabled=True,
        ),
        current_user="admin",
        db=object(),
    )

    assert result == {"ok": True}
    assert saved == [{
        "anthropic": {
            "enabled": True,
        },
        "deepseek": {
            "base_url": "https://gateway.example.invalid/v1",
            "model": "deepseek-chat",
            "enabled": True,
        }
    }]


def test_production_runtime_ignores_legacy_file_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        llm_store,
        "load_configs",
        lambda: {
            "deepseek": {
                "api_key": "legacy-file-secret",
                "base_url": "https://gateway.example.invalid/v1",
                "model": "deepseek-chat",
                "enabled": True,
            }
        },
    )

    result = llm_store.get_provider_config("deepseek")

    assert result == {
        "api_key": "",
        "base_url": "https://gateway.example.invalid/v1",
        "model": "deepseek-chat",
        "enabled": True,
    }


def test_production_runtime_ignores_file_api_key_even_if_fallback_is_enabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_FILE_SECRET_FALLBACK", "true")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        llm_store,
        "load_configs",
        lambda: {
            "deepseek": {
                "base_url": "https://gateway.example.invalid/v1",
                "model": "deepseek-chat",
                "enabled": True,
            }
        },
    )
    monkeypatch.setattr(
        runtime_settings,
        "get_llm_file_configs",
        lambda: {"deepseek": {"api_key": "legacy-file-secret"}},
    )

    result = llm_store.get_provider_config("deepseek")

    assert result["api_key"] == ""


def test_production_test_endpoint_rejects_request_api_key_without_leaking(monkeypatch):
    import openai

    secret = "request-only-secret"
    provider_calls = 0

    def unexpected_openai(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        raise RuntimeError("unexpected provider call")

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(openai, "OpenAI", unexpected_openai)

    with pytest.raises(HTTPException) as caught:
        llm_router.test_config(
            "deepseek",
            llm_router.LLMTestPayload(
                api_key=secret,
                base_url="https://gateway.example.invalid/v1",
                model="deepseek-chat",
            ),
            current_user="admin",
            db=object(),
        )

    assert caught.value.status_code == 400
    assert "环境变量" in caught.value.detail
    assert provider_calls == 0
    assert secret not in caught.value.detail
    assert secret not in repr(caught.value)


def test_production_test_endpoint_sanitizes_provider_failure(monkeypatch):
    import openai

    secret = "environment-only-secret"
    captured: dict[str, str] = {}

    class _Completions:
        def create(self, **_kwargs):
            raise RuntimeError(f"provider rejected {secret}")

    class _Client:
        def __init__(self):
            self.chat = type("_Chat", (), {"completions": _Completions()})()

    def fake_openai(*, api_key: str, base_url: str):
        captured.update(api_key=api_key, base_url=base_url)
        return _Client()

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(
        llm_router,
        "get_provider_config",
        lambda _provider: {
            "api_key": secret,
            "base_url": "https://gateway.example.invalid/v1",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )
    monkeypatch.setattr(openai, "OpenAI", fake_openai)

    with pytest.raises(HTTPException) as caught:
        llm_router.test_config(
            "deepseek",
            llm_router.LLMTestPayload(api_key="***"),
            current_user="admin",
            db=object(),
        )

    assert captured == {
        "api_key": secret,
        "base_url": "https://gateway.example.invalid/v1",
    }
    assert caught.value.status_code == 400
    assert caught.value.detail == "连接失败，请检查服务配置"
    assert secret not in repr(caught.value)


def test_production_reports_environment_api_key_without_exposing_it(monkeypatch):
    secret = "environment-only-secret"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(
        llm_router,
        "load_configs",
        lambda: {"deepseek": {"enabled": True}},
    )

    result = llm_router.list_configs(current_user="admin", db=object())
    deepseek = next(item for item in result if item["provider"] == "deepseek")

    assert deepseek["api_key_set"] is True
    assert secret not in repr(result)
