import asyncio
import threading
from types import SimpleNamespace

import pytest

from app.services.realtime_asr import DashScopeRealtimeAsr
from app.settings import AsrSettings


class FakeRecognition:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.start_kwargs = None
        self.frames = []
        self.stopped = False
        type(self).instances.append(self)

    def start(self, **kwargs):
        self.start_kwargs = kwargs

    def send_audio_frame(self, frame):
        self.frames.append(frame)

    def stop(self):
        self.stopped = True
        self.callback.on_complete()


def _settings(
    *,
    model="fun-asr-realtime",
    context_enabled=True,
    stop_timeout_seconds=0.2,
):
    return AsrSettings(
        realtime_model=model,
        context_enabled=context_enabled,
        packet_duration_ms=100,
        stop_timeout_seconds=stop_timeout_seconds,
        heartbeat_enabled=True,
    )


def _result(*, sentence=None, status_code=200, message="", request_id="req-1"):
    return SimpleNamespace(
        status_code=status_code,
        output=SimpleNamespace(sentence=sentence) if sentence is not None else None,
        message=message,
        request_id=request_id,
    )


def test_fun_asr_start_passes_bounded_context():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "项" * 500,
            recognition_factory=FakeRecognition,
        )

        await session.start()

        recognition = FakeRecognition.instances[-1]
        assert recognition.kwargs["model"] == "fun-asr-realtime"
        assert recognition.kwargs["format"] == "pcm"
        assert recognition.kwargs["sample_rate"] == 16000
        assert recognition.kwargs["language_hints"] == ["zh"]
        assert recognition.kwargs["heartbeat"] is True
        assert recognition.kwargs["api_key"] == "secret"
        raw_input = recognition.start_kwargs["raw_input"]
        text = raw_input["context"][0]["content"][0]["text"]
        assert raw_input == {
            "context": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                }
            ]
        }
        assert text == "项" * 400
        await session.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("model", "context_enabled"),
    [
        ("paraformer-realtime-v2", True),
        ("fun-asr-realtime", False),
    ],
)
def test_start_omits_raw_input_when_context_is_not_supported(model, context_enabled):
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(model=model, context_enabled=context_enabled),
            "项目上下文",
            recognition_factory=FakeRecognition,
        )

        await session.start()

        assert FakeRecognition.instances[-1].start_kwargs == {}
        await session.stop()

    asyncio.run(scenario())


def test_partial_and_final_events_keep_a_stable_segment_id():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()
        callback = FakeRecognition.instances[-1].callback

        def publish_events():
            callback.on_event(
                _result(
                    sentence={
                        "text": "今天完成",
                        "sentence_end": False,
                        "begin_time": 10,
                        "end_time": 20,
                    }
                )
            )
            callback.on_event(
                _result(
                    sentence={
                        "text": "今天完成开发",
                        "sentence_end": True,
                        "begin_time": 10,
                        "end_time": 30,
                    }
                )
            )
            callback.on_event(
                _result(
                    sentence={
                        "text": "明天联调",
                        "sentence_end": False,
                        "begin_time": 31,
                        "end_time": 40,
                    }
                )
            )

        thread = threading.Thread(target=publish_events)
        thread.start()
        thread.join()

        partial = await session.next_event()
        final = await session.next_event()
        following = await session.next_event()
        assert partial == {
            "type": "transcript",
            "segment_id": "seg-0",
            "text": "今天完成",
            "final": False,
            "begin_time": 10,
            "end_time": 20,
        }
        assert final["segment_id"] == "seg-0"
        assert final["final"] is True
        assert following["segment_id"] == "seg-1"
        await session.stop()

    asyncio.run(scenario())


def test_stop_sends_audio_and_waits_for_completion():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()

        await session.send_audio(b"\x01\x02")
        await session.stop()

        recognition = FakeRecognition.instances[-1]
        assert recognition.frames == [b"\x01\x02"]
        assert recognition.stopped is True
        assert session.completed.is_set()
        assert await session.next_event() is None

    asyncio.run(scenario())


def test_provider_error_is_exposed_as_retryable_event():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()

        FakeRecognition.instances[-1].callback.on_error(
            _result(status_code=500, message="provider unavailable", request_id="req-9")
        )

        assert await session.next_event() == {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": "provider unavailable",
            "request_id": "req-9",
            "retryable": True,
        }
        assert session.completed.is_set()
        await session.stop()

    asyncio.run(scenario())


def test_non_success_event_is_exposed_as_provider_error():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()

        FakeRecognition.instances[-1].callback.on_event(
            _result(status_code=429, message="rate limited", request_id="req-10")
        )

        event = await session.next_event()
        assert event["code"] == "ASR_PROVIDER_ERROR"
        assert event["request_id"] == "req-10"
        assert session.completed.is_set()
        await session.stop()

    asyncio.run(scenario())


def test_empty_sentence_is_ignored():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()
        callback = FakeRecognition.instances[-1].callback
        callback.on_event(_result(sentence={"text": "  ", "sentence_end": False}))
        callback.on_event(
            _result(sentence={"text": "有效内容", "sentence_end": True})
        )

        assert (await session.next_event())["text"] == "有效内容"
        await session.stop()

    asyncio.run(scenario())


def test_send_audio_before_start_raises():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )

        with pytest.raises(RuntimeError, match="not started"):
            await session.send_audio(b"audio")

    asyncio.run(scenario())


def test_stop_before_start_closes_event_stream():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )

        await session.stop()

        assert await session.next_event() is None

    asyncio.run(scenario())
