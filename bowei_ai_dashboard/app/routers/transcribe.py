"""Audio transcription routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import tempfile
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from ..auth import get_session_user
from ..database import get_db
from ..llm_config import get_provider_config
from ..permissions import get_current_user_name
from ..services.asr_context import build_work_report_asr_context
from ..services.realtime_asr import DashScopeRealtimeAsr
from ..settings import get_asr_settings, get_settings

router = APIRouter(prefix="/api/transcribe", tags=["transcribe"])
logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {
    ".mp3",
    ".mp4",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".m4a",
    ".wma",
    ".amr",
    ".webm",
}
_MAX_SESSION_AUDIO_BYTES = 16000 * 2 * 60 * 60 * 4
_CLEANUP_GRACE_SECONDS = 0.1


class StreamStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["start"]
    scene: Literal["work_report"]
    project_id: int = Field(gt=0)
    selected_task_id: int = Field(gt=0)
    sample_rate: Literal[16000]
    format: Literal["pcm"]


def _detect_format(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    fmt_map = {
        ".mp3": "mp3",
        ".wav": "wav",
        ".flac": "flac",
        ".aac": "aac",
        ".ogg": "ogg-opus",
        ".m4a": "m4a",
        ".wma": "wma",
        ".amr": "amr",
        ".webm": "opus",
        ".mp4": "mp4",
    }
    return fmt_map.get(ext, "mp3")


def _do_transcribe(file_bytes: bytes, filename: str, api_key: str) -> str:
    import dashscope
    from dashscope.audio.asr import Recognition

    dashscope.api_key = api_key
    suffix = os.path.splitext(filename)[1].lower() or ".mp3"
    fmt = _detect_format(filename)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        recognition = Recognition(
            model="paraformer-realtime-v2",
            format=fmt,
            sample_rate=16000,
            language_hints=["zh", "en"],
            api_key=api_key,
            callback=None,
        )
        result = recognition.call(tmp_path)
        if result.status_code != 200:
            raise RuntimeError(
                f"转写失败（{result.status_code}）: {result.message}"
            )

        output = result.output or {}
        sentences = output.get("sentence") or []
        if sentences:
            return "".join(
                sentence.get("text", "")
                for sentence in sentences
                if sentence.get("text")
            )
        return output.get("text", "")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("")
async def transcribe(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_name),
):
    filename = file.filename or "audio.mp3"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _SUPPORTED_FORMATS:
        raise HTTPException(422, f"不支持的音频格式: {ext}")

    api_key = get_provider_config("dashscope").get("api_key", "")
    if not api_key:
        raise HTTPException(
            500,
            "未配置 Dashscope API Key，请在系统设置中填写",
        )

    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(413, "文件过大，最大支持 200MB")

    try:
        text = await asyncio.to_thread(
            _do_transcribe,
            content,
            filename,
            api_key,
        )
        return {"text": text, "filename": filename}
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


async def run_transcribe_stream(
    websocket,
    *,
    current_user: str,
    db: Session,
    context_builder=build_work_report_asr_context,
    asr_factory=DashScopeRealtimeAsr,
    api_key: str,
) -> None:
    """Coordinate one authenticated work-report transcription session."""
    settings = get_asr_settings()
    loop = asyncio.get_running_loop()
    outbound: asyncio.Queue[
        tuple[dict[str, Any], asyncio.Future[None]] | None
    ] = asyncio.Queue()
    writer_task: asyncio.Task[None]

    async def write_outbound() -> None:
        while True:
            item = await outbound.get()
            if item is None:
                return
            payload, acknowledgement = item
            try:
                await websocket.send_json(payload)
            except BaseException as exc:
                if not acknowledgement.done():
                    acknowledgement.set_exception(exc)
                while True:
                    try:
                        pending = outbound.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if pending is not None and not pending[1].done():
                        pending[1].set_exception(exc)
                raise
            else:
                if not acknowledgement.done():
                    acknowledgement.set_result(None)

    writer_task = asyncio.create_task(write_outbound())

    async def emit(
        payload: dict[str, Any],
        *,
        deadline: float | None = None,
    ) -> None:
        if writer_task.done():
            await writer_task
            raise RuntimeError("websocket writer stopped")
        acknowledgement = loop.create_future()
        outbound.put_nowait((payload, acknowledgement))
        timeout = settings.stop_timeout_seconds
        if deadline is not None:
            timeout = max(0.0, deadline - loop.time())
        await asyncio.wait_for(acknowledgement, timeout=timeout)

    session = None
    session_started = False
    session_failed = False
    terminal_error = False
    explicit_stop = False
    transport_failed = False
    cleanup_deadline: float | None = None
    packet_count = 0
    audio_bytes = 0
    queue_peak = 0
    started_at = time.monotonic()
    first_result_at: float | None = None
    stop_started_at = time.monotonic()
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
    audio_task: asyncio.Task[None] | None = None
    result_task: asyncio.Task[None] | None = None
    receive_task: asyncio.Task[dict] | None = None
    stop_task: asyncio.Task[None] | None = None

    async def emit_terminal_error(
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        nonlocal session_failed, terminal_error
        session_failed = True
        if terminal_error or transport_failed:
            return
        terminal_error = True
        await emit(
            {
                "type": "error",
                "code": code,
                "message": message,
                "retryable": retryable,
            }
        )

    async def send_results() -> None:
        nonlocal first_result_at, session_failed, terminal_error
        while True:
            event = await session.next_event()
            if event is None:
                return
            if event.get("type") == "error":
                request_id = str(event.get("request_id") or "")
                logger.warning(
                    "ASR provider event code=%s request_id=%s",
                    "ASR_PROVIDER_ERROR",
                    request_id,
                )
                session_failed = True
                if not terminal_error:
                    terminal_error = True
                    await emit(
                        {
                            "type": "error",
                            "code": "ASR_PROVIDER_ERROR",
                            "message": "语音识别服务发生错误，请重试",
                            "retryable": bool(event.get("retryable", True)),
                        }
                    )
                return
            if terminal_error:
                continue
            if first_result_at is None and event.get("type") == "transcript":
                first_result_at = time.monotonic()
            safe_event = {
                key: value
                for key, value in event.items()
                if key != "request_id"
            }
            await emit(safe_event)

    async def send_audio() -> None:
        while True:
            data = await audio_queue.get()
            if data is None:
                return
            await session.send_audio(data)

    def remaining(deadline: float) -> float:
        return max(0.0, deadline - loop.time())

    async def cancel_tasks(*tasks: asyncio.Task | None) -> None:
        current = asyncio.current_task()
        pending = [
            task
            for task in tasks
            if task is not None and task is not current and not task.done()
        ]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def cleanup_session() -> None:
        nonlocal session_failed, cleanup_deadline, stop_task
        if not session_started or session is None:
            return
        cleanup_deadline = (
            loop.time()
            + settings.stop_timeout_seconds
            + _CLEANUP_GRACE_SECONDS
        )
        await cancel_tasks(receive_task)
        phase_budget = max(
            0.01,
            (
                settings.stop_timeout_seconds
                + _CLEANUP_GRACE_SECONDS
            )
            / 3,
        )

        try:
            await asyncio.wait_for(
                audio_queue.put(None),
                timeout=min(remaining(cleanup_deadline), phase_budget),
            )
            if audio_task is not None:
                await asyncio.wait_for(
                    asyncio.shield(audio_task),
                    timeout=min(remaining(cleanup_deadline), phase_budget),
                )
        except Exception:
            session_failed = True
            await cancel_tasks(audio_task)

        stop_task = asyncio.create_task(session.stop())
        try:
            await asyncio.wait_for(
                asyncio.shield(stop_task),
                timeout=remaining(cleanup_deadline),
            )
        except Exception:
            session_failed = True
            await cancel_tasks(stop_task)

        if result_task is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(result_task),
                    timeout=remaining(cleanup_deadline),
                )
            except Exception:
                session_failed = True
                await cancel_tasks(result_task)

        await cancel_tasks(audio_task, result_task, receive_task, stop_task)

    async def cleanup_session_safely() -> None:
        cleanup_task = asyncio.create_task(cleanup_session())
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            await cleanup_task
            raise

    async def shutdown_writer() -> None:
        nonlocal cleanup_deadline
        if writer_task.done():
            await asyncio.gather(writer_task, return_exceptions=True)
            return
        if cleanup_deadline is None:
            cleanup_deadline = (
                loop.time()
                + settings.stop_timeout_seconds
                + _CLEANUP_GRACE_SECONDS
            )
        outbound.put_nowait(None)
        try:
            await asyncio.wait_for(
                asyncio.shield(writer_task),
                timeout=remaining(cleanup_deadline),
            )
        except asyncio.CancelledError:
            await cancel_tasks(writer_task)
            raise
        except Exception:
            await cancel_tasks(writer_task)

    try:
        try:
            await emit({"type": "ready"})
            try:
                first = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError, ConnectionError):
                transport_failed = True
                return
            try:
                start = StreamStart.model_validate_json(first.get("text") or "")
            except (ValidationError, ValueError, TypeError, AttributeError):
                await emit_terminal_error(
                    "PROTOCOL_ERROR",
                    "录音启动参数无效，请重新开始",
                    retryable=False,
                )
                return

            try:
                context = (
                    context_builder(
                        current_user,
                        start.project_id,
                        start.selected_task_id,
                        db,
                    )
                    if settings.context_enabled
                    else ""
                )
            except HTTPException as exc:
                await emit_terminal_error(
                    (
                        "CONTEXT_FORBIDDEN"
                        if exc.status_code == 403
                        else "CONTEXT_INVALID"
                    ),
                    "当前项目或关键任务不可用于录音汇报",
                    retryable=False,
                )
                return
            except Exception:
                logger.warning("ASR context validation failed")
                await emit_terminal_error(
                    "CONTEXT_INVALID",
                    "当前项目或关键任务不可用于录音汇报",
                    retryable=False,
                )
                return

            session = asr_factory(
                api_key=api_key,
                settings=settings,
                context=context,
            )
            try:
                await session.start()
            except Exception:
                logger.warning("ASR session start failed")
                await emit_terminal_error(
                    "ASR_START_FAILED",
                    "语音识别服务启动失败，请重试",
                    retryable=True,
                )
                return

            session_started = True
            session_id = secrets.token_urlsafe(18)
            await emit(
                {
                    "type": "started",
                    "model": settings.realtime_model,
                    "session_id": session_id,
                }
            )

            audio_task = asyncio.create_task(send_audio())
            result_task = asyncio.create_task(send_results())
            receive_task = asyncio.create_task(websocket.receive())
            max_packet_bytes = (
                start.sample_rate
                * 2
                * settings.packet_duration_ms
                // 1000
                * 2
            )

            while True:
                watched = {
                    task
                    for task in (
                        receive_task,
                        audio_task,
                        result_task,
                        writer_task,
                    )
                    if task is not None
                }
                done, _ = await asyncio.wait(
                    watched,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if writer_task in done:
                    transport_failed = True
                    session_failed = True
                    if not writer_task.cancelled():
                        await asyncio.gather(
                            writer_task,
                            return_exceptions=True,
                        )
                    break

                if audio_task in done:
                    audio_error = (
                        None
                        if audio_task.cancelled()
                        else audio_task.exception()
                    )
                    if audio_error is not None or not terminal_error:
                        await emit_terminal_error(
                            "ASR_STREAM_FAILED",
                            "语音识别音频流处理失败，请重试",
                            retryable=True,
                        )
                    break

                if result_task in done:
                    result_error = (
                        None
                        if result_task.cancelled()
                        else result_task.exception()
                    )
                    if result_error is not None:
                        await emit_terminal_error(
                            "ASR_STREAM_FAILED",
                            "语音识别结果流处理失败，请重试",
                            retryable=True,
                        )
                    elif not terminal_error:
                        await emit_terminal_error(
                            "ASR_STREAM_FAILED",
                            "语音识别结果流提前结束，请重试",
                            retryable=True,
                        )
                    break

                if receive_task not in done:
                    continue
                try:
                    message = receive_task.result()
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    transport_failed = True
                    session_failed = True
                    break
                receive_task = None

                if message.get("type") == "websocket.disconnect":
                    transport_failed = True
                    session_failed = True
                    break

                if message.get("bytes") is not None:
                    data = message["bytes"]
                    if (
                        not data
                        or len(data) % 2
                        or len(data) > max_packet_bytes
                        or audio_bytes + len(data) > _MAX_SESSION_AUDIO_BYTES
                    ):
                        await emit_terminal_error(
                            "AUDIO_PACKET_INVALID",
                            "音频数据包无效，请重新开始录音",
                            retryable=False,
                        )
                        break
                    packet_count += 1
                    audio_bytes += len(data)
                    try:
                        audio_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        await emit_terminal_error(
                            "AUDIO_BACKPRESSURE",
                            "网络或语音服务积压过高，请检查已有文字后重试",
                            retryable=True,
                        )
                        break
                    queue_peak = max(queue_peak, audio_queue.qsize())
                    receive_task = asyncio.create_task(websocket.receive())
                    continue

                raw = message.get("text") or ""
                try:
                    control = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    control = {}
                if raw == "stop" or (
                    isinstance(control, dict)
                    and control.get("type") == "stop"
                    and set(control) == {"type"}
                ):
                    explicit_stop = True
                    break
                await emit_terminal_error(
                    "PROTOCOL_ERROR",
                    "录音消息顺序无效",
                    retryable=False,
                )
                break

            stop_started_at = time.monotonic()
            try:
                await cleanup_session_safely()
            finally:
                session_started = False
            if (
                explicit_stop
                and not session_failed
                and not terminal_error
                and not transport_failed
            ):
                await emit(
                    {
                        "type": "done",
                        "session_id": session_id,
                        "duration_ms": audio_bytes * 1000 // (16000 * 2),
                    },
                    deadline=cleanup_deadline,
                )
                logger.info(
                    "ASR session complete session_id=%s model=%s packets=%d "
                    "audio_ms=%d queue_peak=%d first_result_ms=%s "
                    "stop_done_ms=%d",
                    session_id,
                    settings.realtime_model,
                    packet_count,
                    audio_bytes * 1000 // (16000 * 2),
                    queue_peak,
                    (
                        round((first_result_at - started_at) * 1000)
                        if first_result_at is not None
                        else None
                    ),
                    round((time.monotonic() - stop_started_at) * 1000),
                )
        except (WebSocketDisconnect, RuntimeError, ConnectionError, TimeoutError):
            transport_failed = True
            session_failed = True
            return
    finally:
        try:
            if session_started:
                await cleanup_session_safely()
        finally:
            await shutdown_writer()


@router.websocket("/stream")
async def transcribe_stream(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """Authenticate and run one realtime work-report transcription stream."""
    await websocket.accept()
    session_id = websocket.cookies.get(get_settings().session_cookie_name)
    username = get_session_user(session_id) if session_id else None
    if not username:
        await websocket.send_json(
            {
                "type": "error",
                "code": "UNAUTHENTICATED",
                "message": "未登录，请重新登录后重试",
                "retryable": False,
            }
        )
        await websocket.close(code=4001)
        return

    api_key = get_provider_config("dashscope").get("api_key", "")
    if not api_key:
        await websocket.send_json(
            {
                "type": "error",
                "code": "ASR_NOT_CONFIGURED",
                "message": "未配置语音识别服务，请联系管理员",
                "retryable": False,
            }
        )
        await websocket.close(code=4002)
        return

    try:
        await run_transcribe_stream(
            websocket,
            current_user=username,
            db=db,
            api_key=api_key,
        )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
