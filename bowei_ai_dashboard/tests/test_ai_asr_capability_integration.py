from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile

from app.ai.contracts import AICapabilityNotConfigured
from app.routers import transcribe
from app.settings import get_settings


class FakeAIService:
    def __init__(self, captured: dict, *, error: Exception | None = None):
        self.captured = captured
        self.error = error

    def transcribe_file(self, capability_key, _content, _filename, context):
        if self.error:
            raise self.error
        self.captured["capability_key"] = capability_key
        self.captured["resource_type"] = context.resource_type
        return SimpleNamespace(text="转写内容")

    def create_realtime_asr_session(self, capability_key, **_kwargs):
        if self.error:
            raise self.error
        self.captured["capability_key"] = capability_key
        return object()


class RouteWebSocket:
    def __init__(self):
        self.cookies = {get_settings().session_cookie_name: "session"}
        self.sent: list[dict] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self):
        return None

    async def send_json(self, value):
        self.sent.append(value)

    async def close(self, *, code=1000, reason=""):
        self.closed = (code, reason)


def test_file_transcription_uses_speech_realtime_capability(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(transcribe, "AIService", lambda _db: FakeAIService(captured))
    upload = UploadFile(filename="a.mp3", file=BytesIO(b"audio"))

    result = asyncio.run(transcribe.transcribe(file=upload, current_user="member", db=object()))

    assert result["text"] == "转写内容"
    assert captured["capability_key"] == "speech.realtime"
    assert captured["resource_type"] == "transcription_file"


def test_realtime_stream_reports_not_configured_without_reading_legacy_provider(monkeypatch):
    websocket = RouteWebSocket()
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    monkeypatch.setattr(
        transcribe,
        "AIService",
        lambda _db: FakeAIService({}, error=AICapabilityNotConfigured()),
    )

    asyncio.run(transcribe.transcribe_stream(websocket, db=object()))

    assert websocket.sent[0]["code"] == "ASR_NOT_CONFIGURED"
