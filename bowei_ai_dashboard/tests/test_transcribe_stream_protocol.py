from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.websockets import WebSocketDisconnect

from app.routers.transcribe import run_transcribe_stream
from app.services.realtime_asr import AsrStartError


def _start_message(**overrides) -> dict:
    payload = {
        "type": "start",
        "scene": "work_report",
        "project_id": 12,
        "selected_task_id": 86,
        "sample_rate": 16000,
        "format": "pcm",
    }
    payload.update(overrides)
    return {
        "type": "websocket.receive",
        "text": json.dumps(payload),
    }


def _audio(data: bytes = b"\x01\x02") -> dict:
    return {"type": "websocket.receive", "bytes": data}


def _stop() -> dict:
    return {"type": "websocket.receive", "text": '{"type":"stop"}'}


class FakeWebSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent: list[dict] = []

    async def receive(self):
        if not self.incoming:
            return {"type": "websocket.disconnect"}
        return self.incoming.pop(0)

    async def send_json(self, item):
        self.sent.append(item)


class FakeAsr:
    def __init__(
        self,
        *,
        events: list[dict] | None = None,
        start_error: Exception | None = None,
        send_delay: float = 0,
    ):
        self.frames: list[bytes] = []
        self.events: asyncio.Queue = asyncio.Queue()
        for event in events or []:
            self.events.put_nowait(event)
        self.start_error = start_error
        self.send_delay = send_delay
        self.started = False
        self.stopped = False
        self.stop_frame_count: int | None = None

    async def start(self):
        if self.start_error:
            raise self.start_error
        self.started = True

    async def send_audio(self, data):
        if self.send_delay:
            await asyncio.sleep(self.send_delay)
        self.frames.append(data)

    async def next_event(self):
        return await self.events.get()

    async def stop(self):
        self.stopped = True
        self.stop_frame_count = len(self.frames)
        await self.events.put(None)


async def _run(
    incoming,
    *,
    asr: FakeAsr | None = None,
    context_builder=lambda *args: "context",
):
    ws = FakeWebSocket(incoming)
    session = asr or FakeAsr()
    factory_calls: list[dict] = []

    def factory(**kwargs):
        factory_calls.append(kwargs)
        return session

    await run_transcribe_stream(
        ws,
        current_user="member",
        db=object(),
        context_builder=context_builder,
        asr_factory=factory,
        api_key="key",
    )
    return ws, session, factory_calls


def test_stream_sends_ready_started_audio_stop_and_done_in_order():
    async def scenario():
        ws, asr, calls = await _run([_start_message(), _audio(), _stop()])

        assert [item["type"] for item in ws.sent] == ["ready", "started", "done"]
        assert ws.sent[1]["model"]
        assert ws.sent[1]["session_id"]
        assert ws.sent[2]["session_id"] == ws.sent[1]["session_id"]
        assert ws.sent[2]["duration_ms"] == 0
        assert asr.frames == [b"\x01\x02"]
        assert asr.stopped is True
        assert calls[0]["api_key"] == "key"
        assert calls[0]["context"] == "context"

    asyncio.run(scenario())


def test_stream_requires_start_before_binary():
    async def scenario():
        ws, asr, _ = await _run([_audio()])

        assert ws.sent[0] == {"type": "ready"}
        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"
        assert ws.sent[-1]["retryable"] is False
        assert asr.started is False
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(scenario())


def test_stream_rejects_meeting_scene():
    async def scenario():
        ws, asr, _ = await _run([
            _start_message(scene="meeting_minutes"),
        ])

        assert ws.sent[-1]["type"] == "error"
        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"
        assert ws.sent[-1]["retryable"] is False
        assert asr.started is False

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "overrides",
    [
        {"project_id": 0},
        {"selected_task_id": -1},
        {"sample_rate": 8000},
        {"format": "wav"},
        {"unexpected": True},
    ],
)
def test_stream_rejects_invalid_start_fields(overrides):
    async def scenario():
        ws, asr, _ = await _run([_start_message(**overrides)])

        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"
        assert asr.started is False

    asyncio.run(scenario())


def test_stream_maps_context_permission_failure():
    def forbidden(*_args):
        raise HTTPException(status_code=403, detail="denied")

    async def scenario():
        ws, asr, _ = await _run([_start_message()], context_builder=forbidden)

        assert ws.sent[-1]["code"] == "CONTEXT_FORBIDDEN"
        assert ws.sent[-1]["retryable"] is False
        assert asr.started is False

    asyncio.run(scenario())


def test_stream_maps_other_context_failure():
    def invalid(*_args):
        raise HTTPException(status_code=404, detail="missing")

    async def scenario():
        ws, asr, _ = await _run([_start_message()], context_builder=invalid)

        assert ws.sent[-1]["code"] == "CONTEXT_INVALID"
        assert ws.sent[-1]["retryable"] is False
        assert asr.started is False

    asyncio.run(scenario())


def test_stream_skips_context_builder_when_context_is_disabled(monkeypatch):
    monkeypatch.setenv("ASR_CONTEXT_ENABLED", "false")

    def must_not_run(*_args):
        raise AssertionError("context builder should be disabled")

    async def scenario():
        ws, _, calls = await _run(
            [_start_message(), _stop()],
            context_builder=must_not_run,
        )

        assert ws.sent[-1]["type"] == "done"
        assert calls[0]["context"] == ""

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure",
    [AsrStartError("provider rejected start"), RuntimeError("unexpected")],
)
def test_stream_start_failure_has_stable_error_without_started_or_done(failure):
    async def scenario():
        ws, _, _ = await _run(
            [_start_message()],
            asr=FakeAsr(start_error=failure),
        )

        assert ws.sent[-1]["code"] == "ASR_START_FAILED"
        assert ws.sent[-1]["retryable"] is True
        assert all(item["type"] not in {"started", "done"} for item in ws.sent)
        assert "request_id" not in ws.sent[-1]

    asyncio.run(scenario())


def test_stream_sends_final_transcript_before_done_and_strips_request_id():
    transcript = {
        "type": "transcript",
        "segment_id": "seg-0",
        "text": "完成汇报",
        "final": True,
        "request_id": "provider-secret-id",
    }

    async def scenario():
        ws, _, _ = await _run(
            [_start_message(), _stop()],
            asr=FakeAsr(events=[transcript]),
        )

        assert [item["type"] for item in ws.sent] == [
            "ready",
            "started",
            "transcript",
            "done",
        ]
        assert "request_id" not in ws.sent[2]

    asyncio.run(scenario())


def test_stream_strips_request_id_from_provider_error():
    provider_error = {
        "type": "error",
        "code": "ASR_PROVIDER_ERROR",
        "message": "provider failed",
        "request_id": "provider-secret-id",
        "retryable": True,
    }

    async def scenario():
        ws, _, _ = await _run(
            [_start_message(), _stop()],
            asr=FakeAsr(events=[provider_error]),
        )

        error = next(item for item in ws.sent if item["type"] == "error")
        assert "request_id" not in error
        assert [item["type"] for item in ws.sent] == [
            "ready",
            "started",
            "error",
        ]

    asyncio.run(scenario())


def test_stream_does_not_send_done_when_stop_produces_provider_error():
    class StopErrorAsr(FakeAsr):
        async def stop(self):
            self.stopped = True
            self.stop_frame_count = len(self.frames)
            await self.events.put(
                {
                    "type": "error",
                    "code": "ASR_PROVIDER_ERROR",
                    "message": "stop failed",
                    "request_id": "provider-secret-id",
                    "retryable": True,
                }
            )
            await self.events.put(None)

    async def scenario():
        ws, _, _ = await _run(
            [_start_message(), _stop()],
            asr=StopErrorAsr(),
        )

        assert [item["type"] for item in ws.sent] == [
            "ready",
            "started",
            "error",
        ]
        assert "request_id" not in ws.sent[-1]

    asyncio.run(scenario())


def test_stream_backpressure_reports_error_and_never_done():
    async def scenario():
        packets = [_audio(bytes([index % 256, 0])) for index in range(55)]
        ws, asr, _ = await _run(
            [_start_message(), *packets],
            asr=FakeAsr(send_delay=0.001),
        )

        assert any(
            item.get("code") == "AUDIO_BACKPRESSURE" for item in ws.sent
        )
        assert all(item["type"] != "done" for item in ws.sent)
        assert asr.stopped is True

    asyncio.run(scenario())


def test_stream_protocol_error_after_start_stops_without_done():
    async def scenario():
        ws, asr, _ = await _run([
            _start_message(),
            {"type": "websocket.receive", "text": '{"type":"pause"}'},
        ])

        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"
        assert asr.stopped is True
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(scenario())


def test_stream_drains_audio_queue_before_stopping_asr():
    async def scenario():
        packets = [_audio(b"\x01\x02") for _ in range(10)]
        ws, asr, _ = await _run(
            [_start_message(), *packets, _stop()],
            asr=FakeAsr(send_delay=0.001),
        )

        assert ws.sent[-1]["type"] == "done"
        assert len(asr.frames) == len(packets)
        assert asr.stop_frame_count == len(packets)

    asyncio.run(scenario())


def test_stream_disconnect_stops_without_done():
    async def scenario():
        ws, asr, _ = await _run([
            _start_message(),
            {"type": "websocket.disconnect"},
        ])

        assert asr.stopped is True
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(scenario())


def test_stream_cancellation_stops_session_and_does_not_leave_tasks_running():
    class BlockingWebSocket(FakeWebSocket):
        def __init__(self):
            super().__init__([_start_message()])
            self.waiting = asyncio.Event()

        async def receive(self):
            if self.incoming:
                return self.incoming.pop(0)
            self.waiting.set()
            await asyncio.Event().wait()

    async def scenario():
        ws = BlockingWebSocket()
        asr = FakeAsr()
        task = asyncio.create_task(
            run_transcribe_stream(
                ws,
                current_user="member",
                db=object(),
                context_builder=lambda *args: "context",
                asr_factory=lambda **kwargs: asr,
                api_key="key",
            )
        )
        await ws.waiting.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)

        assert asr.stopped is True
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(scenario())


def test_stream_serializes_all_websocket_sends():
    class ConcurrentSendDetectingWebSocket(FakeWebSocket):
        def __init__(self, incoming):
            super().__init__(incoming)
            self.in_send = False

        async def send_json(self, item):
            assert self.in_send is False, "concurrent websocket send"
            self.in_send = True
            try:
                await asyncio.sleep(0)
                self.sent.append(item)
            finally:
                self.in_send = False

    async def scenario():
        ws = ConcurrentSendDetectingWebSocket([
            _start_message(),
            {"type": "websocket.receive", "text": '{"type":"pause"}'},
        ])
        asr = FakeAsr(events=[{
            "type": "transcript",
            "segment_id": "seg-0",
            "text": "partial",
            "final": False,
        }])

        await run_transcribe_stream(
            ws,
            current_user="member",
            db=object(),
            context_builder=lambda *args: "context",
            asr_factory=lambda **kwargs: asr,
            api_key="key",
        )

        assert any(item.get("code") == "PROTOCOL_ERROR" for item in ws.sent)

    asyncio.run(scenario())


def test_stream_send_audio_failure_is_terminal_and_returns():
    class FailingAudioAsr(FakeAsr):
        async def send_audio(self, _data):
            raise RuntimeError("audio provider failed")

    async def scenario():
        ws, asr, _ = await _run(
            [_start_message(), _audio(), _stop()],
            asr=FailingAudioAsr(),
        )

        assert any(item.get("code") == "ASR_STREAM_FAILED" for item in ws.sent)
        assert all(item["type"] != "done" for item in ws.sent)
        assert asr.stopped is True

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


def test_stream_result_failure_is_terminal_and_returns():
    class FailingResultAsr(FakeAsr):
        async def next_event(self):
            raise RuntimeError("result provider failed")

    async def scenario():
        ws, asr, _ = await _run(
            [_start_message(), _stop()],
            asr=FailingResultAsr(),
        )

        assert any(item.get("code") == "ASR_STREAM_FAILED" for item in ws.sent)
        assert all(item["type"] != "done" for item in ws.sent)
        assert asr.stopped is True

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


def test_stream_started_send_disconnect_still_stops_session():
    class DisconnectOnStartedWebSocket(FakeWebSocket):
        async def send_json(self, item):
            if item.get("type") == "started":
                raise WebSocketDisconnect(code=1006)
            await super().send_json(item)

    async def scenario():
        ws = DisconnectOnStartedWebSocket([_start_message()])
        asr = FakeAsr()

        await run_transcribe_stream(
            ws,
            current_user="member",
            db=object(),
            context_builder=lambda *args: "context",
            asr_factory=lambda **kwargs: asr,
            api_key="key",
        )

        assert asr.stopped is True
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


def test_stream_ignores_transcript_after_terminal_provider_error():
    events = [
        {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": "unsafe provider detail",
            "request_id": "request-safe-for-log-only",
            "retryable": True,
        },
        {
            "type": "transcript",
            "segment_id": "seg-late",
            "text": "must not escape",
            "final": True,
        },
    ]

    async def scenario():
        ws, _, _ = await _run(
            [_start_message(), _stop()],
            asr=FakeAsr(events=events),
        )

        assert all(item["type"] != "transcript" for item in ws.sent)
        error = next(item for item in ws.sent if item["type"] == "error")
        assert error["message"] == "语音识别服务发生错误，请重试"
        assert "request_id" not in error

    asyncio.run(scenario())


@pytest.mark.parametrize("bad_packet", [b"\x01", b""])
def test_stream_rejects_empty_or_odd_pcm_packet(bad_packet):
    async def scenario():
        ws, asr, _ = await _run([
            _start_message(),
            _audio(bad_packet),
        ])

        assert ws.sent[-1]["code"] == "AUDIO_PACKET_INVALID"
        assert all(item["type"] != "done" for item in ws.sent)
        assert asr.frames == []

    asyncio.run(scenario())


def test_stream_rejects_oversized_pcm_packet():
    async def scenario():
        ws, asr, _ = await _run([
            _start_message(),
            _audio(b"\x00\x00" * 3201),
        ])

        assert ws.sent[-1]["code"] == "AUDIO_PACKET_INVALID"
        assert all(item["type"] != "done" for item in ws.sent)
        assert asr.frames == []

    asyncio.run(scenario())


def test_stream_cleanup_deadline_handles_stuck_audio_and_result(
    monkeypatch,
):
    from app.routers import transcribe

    original_settings = transcribe.get_asr_settings()
    monkeypatch.setattr(
        transcribe,
        "get_asr_settings",
        lambda: replace(original_settings, stop_timeout_seconds=0.05),
    )

    class StuckAsr(FakeAsr):
        async def send_audio(self, _data):
            await asyncio.Event().wait()

        async def stop(self):
            self.stopped = True

    async def scenario():
        started = time.monotonic()
        ws, asr, _ = await _run(
            [_start_message(), _audio(), _stop()],
            asr=StuckAsr(),
        )

        assert time.monotonic() - started < 0.5
        assert asr.stopped is True
        assert all(item["type"] != "done" for item in ws.sent)

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))
