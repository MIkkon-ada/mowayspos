from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

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


def test_websocket_auth_uses_the_runtime_http_session_cookie_name(monkeypatch):
    websocket = _RejectingWebSocket()
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda session_id: None)

    asyncio.run(transcribe.transcribe_stream(websocket))

    assert websocket.cookies.requested == ["custom_ws_session"]
    assert websocket.closed is not None
    assert websocket.closed[0] == 4001


def test_production_rejects_persisting_api_keys_without_leaking_them(monkeypatch):
    secret = "never-persist-or-return-this-key"
    saved: list[dict] = []
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(llm_router, "load_configs", lambda: {})
    monkeypatch.setattr(llm_router, "save_configs", saved.append)

    with pytest.raises(HTTPException) as caught:
        llm_router.save_config(
            "deepseek",
            llm_router.LLMConfigPayload(
                api_key=secret,
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                enabled=True,
            ),
            current_user="admin",
            db=object(),
        )

    assert caught.value.status_code == 400
    assert "环境变量" in caught.value.detail
    assert secret not in caught.value.detail
    assert secret not in repr(caught.value)
    assert saved == []


def test_production_can_persist_non_secret_provider_settings(monkeypatch):
    saved: list[dict] = []
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(llm_router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(
        llm_router,
        "load_configs",
        lambda: {"deepseek": {"api_key": "legacy-file-secret", "enabled": False}},
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
        "deepseek": {
            "base_url": "https://gateway.example.invalid/v1",
            "model": "deepseek-chat",
            "enabled": True,
        }
    }]


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
