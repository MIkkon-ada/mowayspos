"""Async wrapper around the blocking DashScope realtime ASR SDK."""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable

from app.settings import AsrSettings


class _SessionState(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class DashScopeRealtimeAsr:
    """Expose one DashScope recognition session through async methods/events."""

    def __init__(
        self,
        api_key: str,
        settings: AsrSettings,
        context: str,
        recognition_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.settings = settings
        self.context = context[:400]
        self._recognition_factory = recognition_factory
        self._recognition: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.completed = asyncio.Event()
        self._segment_index = 0
        self._state = _SessionState.NEW
        self._state_lock = asyncio.Lock()
        self._stop_task: asyncio.Task[None] | None = None
        self._callbacks_open = False
        self._terminal_sent = False

    @property
    def state(self) -> str:
        return self._state.value

    async def start(self) -> None:
        """Create and start the provider recognition session."""
        async with self._state_lock:
            if self._state is not _SessionState.NEW:
                raise RuntimeError(
                    f"ASR start requires NEW state; current state is {self.state}"
                )
            self._state = _SessionState.STARTING
            self._loop = asyncio.get_running_loop()
            self._callbacks_open = True
            try:
                factory = self._recognition_factory
                if factory is None:
                    import dashscope
                    from dashscope.audio.asr import Recognition

                    dashscope.api_key = self.api_key
                    factory = Recognition

                self._recognition = factory(
                    model=self.settings.realtime_model,
                    format="pcm",
                    sample_rate=16000,
                    language_hints=["zh"],
                    heartbeat=self.settings.heartbeat_enabled,
                    callback=_RecognitionCallback(self),
                    api_key=self.api_key,
                )
                start_kwargs: dict[str, Any] = {}
                if (
                    self.settings.context_enabled
                    and self.context
                    and self.settings.realtime_model == "fun-asr-realtime"
                ):
                    start_kwargs["raw_input"] = {
                        "context": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": self.context,
                                    }
                                ],
                            }
                        ]
                    }
                await asyncio.to_thread(self._recognition.start, **start_kwargs)
            except Exception as exc:
                self._callbacks_open = False
                await self._best_effort_stop_after_start_failure()
                self._publish_internal_error("ASR_PROVIDER_ERROR", str(exc))
                self._publish_terminal()
                self._state = _SessionState.STOPPED
                return
            self._state = _SessionState.RUNNING

    async def send_audio(self, frame: bytes) -> None:
        """Send one PCM audio frame without blocking the event loop."""
        async with self._state_lock:
            if self._state is not _SessionState.RUNNING or self._recognition is None:
                raise RuntimeError(
                    "ASR session is not started; "
                    f"audio requires RUNNING state; current state is {self.state}"
                )
            await asyncio.to_thread(self._recognition.send_audio_frame, frame)

    async def next_event(self) -> dict[str, Any] | None:
        """Wait for the next transcript/error event, or the terminal sentinel."""
        return await self._events.get()

    async def stop(self) -> None:
        """Stop recognition, wait briefly for callbacks, and close event delivery."""
        async with self._state_lock:
            if self._stop_task is not None:
                stop_task = self._stop_task
            elif self._state is _SessionState.STOPPED:
                return
            elif self._state is _SessionState.NEW:
                self._callbacks_open = False
                self._state = _SessionState.STOPPED
                self._publish_terminal()
                return
            elif self._state is not _SessionState.RUNNING:
                raise RuntimeError(
                    f"ASR stop requires RUNNING state; current state is {self.state}"
                )
            else:
                self._state = _SessionState.STOPPING
                stop_task = asyncio.create_task(self._run_stop())
                self._stop_task = stop_task
        await asyncio.shield(stop_task)

    async def _run_stop(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.settings.stop_timeout_seconds
        recognition = self._recognition
        try:
            provider_stop = asyncio.create_task(asyncio.to_thread(recognition.stop))
            provider_stop.add_done_callback(_consume_task_exception)
            await asyncio.wait_for(
                asyncio.shield(provider_stop),
                timeout=_remaining(deadline, loop),
            )
            if not self.completed.is_set():
                await asyncio.wait_for(
                    self.completed.wait(),
                    timeout=_remaining(deadline, loop),
                )
            await asyncio.sleep(0)
        except TimeoutError:
            self._publish_internal_error(
                "ASR_STOP_TIMEOUT",
                "recognition stop timed out",
            )
        except Exception as exc:
            self._publish_internal_error("ASR_PROVIDER_ERROR", str(exc))
        finally:
            self._callbacks_open = False
            self._publish_terminal()
            async with self._state_lock:
                self._state = _SessionState.STOPPED

    async def _best_effort_stop_after_start_failure(self) -> None:
        if self._recognition is None:
            return
        cleanup = asyncio.create_task(asyncio.to_thread(self._recognition.stop))
        cleanup.add_done_callback(_consume_task_exception)
        try:
            await asyncio.wait_for(
                asyncio.shield(cleanup),
                timeout=min(self.settings.stop_timeout_seconds, 0.25),
            )
        except Exception:
            pass

    def _publish_transcript(self, sentence: Any) -> None:
        text = str(_field(sentence, "text", "") or "").strip()
        if not text:
            return
        is_final = bool(_field(sentence, "sentence_end", False))
        begin_time = _field(sentence, "begin_time")
        end_time = _field(sentence, "end_time")
        loop = self._loop
        if loop is None or not self._callbacks_open:
            return

        def publish() -> None:
            if not self._callbacks_open:
                return
            self._events.put_nowait(
                {
                    "type": "transcript",
                    "segment_id": f"seg-{self._segment_index}",
                    "text": text,
                    "final": is_final,
                    "begin_time": begin_time,
                    "end_time": end_time,
                }
            )
            if is_final:
                self._segment_index += 1

        loop.call_soon_threadsafe(publish)

    def _publish_error(self, result: Any) -> None:
        message = _field(result, "message")
        request_id = _field(result, "request_id")
        event = {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": str(message) if message else "recognition failed",
            "request_id": "" if request_id is None else str(request_id),
            "retryable": _field(result, "status_code") not in (
                401,
                403,
                "401",
                "403",
            ),
        }
        loop = self._loop
        if loop is None or not self._callbacks_open:
            return

        def publish_and_complete() -> None:
            if not self._callbacks_open:
                return
            self._events.put_nowait(event)
            self.completed.set()

        loop.call_soon_threadsafe(publish_and_complete)

    def _mark_completed(self) -> None:
        loop = self._loop
        if loop is None or not self._callbacks_open:
            return

        def mark() -> None:
            if self._callbacks_open:
                self.completed.set()

        loop.call_soon_threadsafe(mark)

    def _publish_internal_error(self, code: str, message: str) -> None:
        self._events.put_nowait(
            {
                "type": "error",
                "code": code,
                "message": message or "recognition failed",
                "request_id": "",
                "retryable": True,
            }
        )

    def _publish_terminal(self) -> None:
        if self._terminal_sent:
            return
        self._terminal_sent = True
        self._events.put_nowait(None)


class _RecognitionCallback:
    def __init__(self, session: DashScopeRealtimeAsr) -> None:
        self._session = session

    def on_open(self) -> None:
        pass

    def on_close(self) -> None:
        pass

    def on_complete(self) -> None:
        self._session._mark_completed()

    def on_error(self, result: Any) -> None:
        self._session._publish_error(result)

    def on_event(self, result: Any) -> None:
        if _field(result, "status_code") != 200:
            self._session._publish_error(result)
            return
        output = _field(result, "output")
        sentence = _field(output, "sentence") if output is not None else None
        if sentence is not None:
            self._session._publish_transcript(sentence)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _remaining(deadline: float, loop: asyncio.AbstractEventLoop) -> float:
    return max(0.0, deadline - loop.time())


def _consume_task_exception(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()
