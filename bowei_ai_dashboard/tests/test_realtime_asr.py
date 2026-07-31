import asyncio
import threading
import time
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


class BlockingStopRecognition(FakeRecognition):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stop_calls = 0
        self.stop_entered = threading.Event()
        self.stop_release = threading.Event()

    def stop(self):
        self.stop_calls += 1
        self.stop_entered.set()
        self.stop_release.wait(timeout=1)
        self.callback.on_event(
            _result(
                sentence={
                    "text": "迟到结果",
                    "sentence_end": True,
                    "begin_time": 1,
                    "end_time": 2,
                }
            )
        )
        self.callback.on_complete()


class StartFailRecognition(FakeRecognition):
    def start(self, **kwargs):
        raise RuntimeError("start exploded")


class StopFailRecognition(FakeRecognition):
    def stop(self):
        self.stopped = True
        raise RuntimeError("stop exploded")


class FinalOnStopRecognition(FakeRecognition):
    def stop(self):
        self.stopped = True
        self.callback.on_event(
            _result(
                sentence={
                    "text": "最终结果",
                    "sentence_end": True,
                    "begin_time": 10,
                    "end_time": 20,
                }
            )
        )
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


@pytest.mark.parametrize(
    "result",
    [
        SimpleNamespace(status_code=500, message=None),
        SimpleNamespace(status_code=500, message="", request_id=None),
    ],
)
def test_provider_error_uses_fallback_message_and_empty_request_id(result):
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()
        FakeRecognition.instances[-1].callback.on_error(result)

        event = await session.next_event()
        assert event["message"] == "recognition failed"
        assert event["request_id"] == ""
        await session.stop()

    asyncio.run(scenario())


def test_provider_error_handles_missing_message_and_normalizes_request_id():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()
        result = SimpleNamespace(status_code=500, request_id=12345)

        FakeRecognition.instances[-1].callback.on_error(result)

        event = await session.next_event()
        assert event["message"] == "recognition failed"
        assert event["request_id"] == "12345"
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


def test_repeated_start_is_rejected():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()

        with pytest.raises(RuntimeError, match="NEW"):
            await session.start()

        await session.stop()

    asyncio.run(scenario())


def test_send_audio_after_stop_is_rejected():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()
        await session.stop()

        with pytest.raises(RuntimeError, match="RUNNING"):
            await session.send_audio(b"late")
        with pytest.raises(RuntimeError, match="NEW"):
            await session.start()

    asyncio.run(scenario())


def test_concurrent_stop_calls_wait_for_one_provider_stop():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(stop_timeout_seconds=0.5),
            "",
            recognition_factory=BlockingStopRecognition,
        )
        await session.start()
        recognition = FakeRecognition.instances[-1]

        first = asyncio.create_task(session.stop())
        assert await asyncio.to_thread(recognition.stop_entered.wait, 0.2)
        second = asyncio.create_task(session.stop())
        await asyncio.sleep(0.02)
        assert not second.done()

        recognition.stop_release.set()
        await asyncio.gather(first, second)
        assert recognition.stop_calls == 1
        assert session.state == "STOPPED"
        assert (await session.next_event())["text"] == "迟到结果"
        assert await session.next_event() is None
        await session.stop()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(session.next_event(), timeout=0.02)

    asyncio.run(scenario())


def test_blocking_provider_stop_times_out_and_ignores_late_final():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(stop_timeout_seconds=0.03),
            "",
            recognition_factory=BlockingStopRecognition,
        )
        await session.start()
        recognition = FakeRecognition.instances[-1]

        started = time.perf_counter()
        await session.stop()
        elapsed = time.perf_counter() - started

        assert elapsed < 0.15
        assert await session.next_event() == {
            "type": "error",
            "code": "ASR_STOP_TIMEOUT",
            "message": "recognition stop timed out",
            "request_id": "",
            "retryable": True,
        }
        assert await session.next_event() is None
        recognition.stop_release.set()
        await asyncio.sleep(0.05)
        recognition.callback.on_error(
            _result(status_code=500, message="late error", request_id="req-late")
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(session.next_event(), timeout=0.02)

    asyncio.run(scenario())


def test_start_exception_is_structured_and_terminal():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=StartFailRecognition,
        )

        await session.start()

        assert await session.next_event() == {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": "start exploded",
            "request_id": "",
            "retryable": True,
        }
        assert await session.next_event() is None
        assert session.state == "STOPPED"

    asyncio.run(scenario())


def test_stop_exception_is_structured_and_terminal():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=StopFailRecognition,
        )
        await session.start()

        await session.stop()

        assert await session.next_event() == {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": "stop exploded",
            "request_id": "",
            "retryable": True,
        }
        assert await session.next_event() is None
        assert session.state == "STOPPED"

    asyncio.run(scenario())


def test_normal_stop_delivers_final_before_terminal_sentinel():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FinalOnStopRecognition,
        )
        await session.start()

        await session.stop()

        final = await session.next_event()
        assert final["type"] == "transcript"
        assert final["text"] == "最终结果"
        assert final["final"] is True
        assert await session.next_event() is None

    asyncio.run(scenario())


def test_authentication_provider_error_is_not_retryable():
    async def scenario():
        session = DashScopeRealtimeAsr(
            "secret",
            _settings(),
            "",
            recognition_factory=FakeRecognition,
        )
        await session.start()

        FakeRecognition.instances[-1].callback.on_event(
            _result(status_code=401, message="unauthorized", request_id="req-auth")
        )

        event = await session.next_event()
        assert event["retryable"] is False
        await session.stop()

    asyncio.run(scenario())
