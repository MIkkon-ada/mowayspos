"""Async wrapper around the blocking DashScope realtime ASR SDK."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.settings import AsrSettings


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
        self._started = False
        self._stopped = False

    async def start(self) -> None:
        """Create and start the provider recognition session."""
        self._loop = asyncio.get_running_loop()
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
        self._started = True

    async def send_audio(self, frame: bytes) -> None:
        """Send one PCM audio frame without blocking the event loop."""
        if not self._started or self._recognition is None:
            raise RuntimeError("ASR session is not started")
        await asyncio.to_thread(self._recognition.send_audio_frame, frame)

    async def next_event(self) -> dict[str, Any] | None:
        """Wait for the next transcript/error event, or the terminal sentinel."""
        return await self._events.get()

    async def stop(self) -> None:
        """Stop recognition, wait briefly for callbacks, and close event delivery."""
        if self._stopped:
            return
        self._stopped = True
        if not self._started or self._recognition is None:
            await self._events.put(None)
            return

        try:
            await asyncio.to_thread(self._recognition.stop)
            if not self.completed.is_set():
                try:
                    await asyncio.wait_for(
                        self.completed.wait(),
                        timeout=self.settings.stop_timeout_seconds,
                    )
                except TimeoutError:
                    pass
        finally:
            await self._events.put(None)

    def _publish_transcript(self, sentence: Any) -> None:
        text = str(_field(sentence, "text", "") or "").strip()
        if not text:
            return
        is_final = bool(_field(sentence, "sentence_end", False))
        event = {
            "type": "transcript",
            "segment_id": f"seg-{self._segment_index}",
            "text": text,
            "final": is_final,
            "begin_time": _field(sentence, "begin_time"),
            "end_time": _field(sentence, "end_time"),
        }
        self._enqueue_threadsafe(event)
        if is_final:
            self._segment_index += 1

    def _publish_error(self, result: Any) -> None:
        event = {
            "type": "error",
            "code": "ASR_PROVIDER_ERROR",
            "message": str(_field(result, "message", "") or ""),
            "request_id": _field(result, "request_id"),
            "retryable": True,
        }
        loop = self._loop
        if loop is None:
            return

        def publish_and_complete() -> None:
            self._events.put_nowait(event)
            self.completed.set()

        loop.call_soon_threadsafe(publish_and_complete)

    def _mark_completed(self) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self.completed.set)

    def _enqueue_threadsafe(self, event: dict[str, Any]) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._events.put_nowait, event)


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
