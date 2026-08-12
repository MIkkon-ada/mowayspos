from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

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


def test_websocket_reports_unconfigured_asr_capability(monkeypatch):
    websocket = _RouteWebSocket()
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    class UnconfiguredAIService:
        def create_realtime_asr_session(self, *_args, **_kwargs):
            from app.ai.contracts import AICapabilityNotConfigured
            raise AICapabilityNotConfigured()

    monkeypatch.setattr(transcribe, "AIService", lambda _db: UnconfiguredAIService())

    asyncio.run(transcribe.transcribe_stream(websocket, db=object()))

    assert websocket._sent == [{
        "type": "error",
        "code": "ASR_NOT_CONFIGURED",
        "message": "未配置语音识别服务，请联系管理员",
        "retryable": False,
    }]
    assert websocket.closed == (4002, "")


def test_websocket_passes_authenticated_user_and_capability_session_to_coordinator(monkeypatch):
    websocket = _RouteWebSocket()
    fake_db = object()
    received: dict = {}

    async def coordinator(_websocket, **kwargs):
        received.update(kwargs)

    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_ws_session")
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    asr_session = object()
    monkeypatch.setattr(
        transcribe,
        "AIService",
        lambda _db: type(
            "ConfiguredAIService",
            (), {"create_realtime_asr_session": lambda self, *_args, **_kwargs: asr_session},
        )(),
    )
    monkeypatch.setattr(transcribe, "run_transcribe_stream", coordinator)

    asyncio.run(transcribe.transcribe_stream(websocket, db=fake_db))

    assert received == {
        "current_user": "member",
        "db": fake_db,
        "asr_session": asr_session,
    }
    assert websocket.closed == (1000, "")
