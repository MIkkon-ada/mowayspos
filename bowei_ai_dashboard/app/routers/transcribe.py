"""Audio transcription routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import tempfile
import time
from typing import Literal

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
    await websocket.send_json({"type": "ready"})
    try:
        first = await websocket.receive()
        start = StreamStart.model_validate_json(first.get("text") or "")
    except (ValidationError, ValueError, TypeError, AttributeError):
        await websocket.send_json(
            {
                "type": "error",
                "code": "PROTOCOL_ERROR",
                "message": "录音启动参数无效，请重新开始",
                "retryable": False,
            }
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
        await websocket.send_json(
            {
                "type": "error",
                "code": (
                    "CONTEXT_FORBIDDEN"
                    if exc.status_code == 403
                    else "CONTEXT_INVALID"
                ),
                "message": "当前项目或关键任务不可用于录音汇报",
                "retryable": False,
            }
        )
        return
    except Exception:
        logger.exception("ASR context validation failed")
        await websocket.send_json(
            {
                "type": "error",
                "code": "CONTEXT_INVALID",
                "message": "当前项目或关键任务不可用于录音汇报",
                "retryable": False,
            }
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
        logger.exception("ASR session start failed")
        await websocket.send_json(
            {
                "type": "error",
                "code": "ASR_START_FAILED",
                "message": "语音识别服务启动失败，请重试",
                "retryable": True,
            }
        )
        return

    session_id = secrets.token_urlsafe(18)
    await websocket.send_json(
        {
            "type": "started",
            "model": settings.realtime_model,
            "session_id": session_id,
        }
    )

    packet_count = 0
    audio_bytes = 0
    queue_peak = 0
    started_at = time.monotonic()
    first_result_at: float | None = None
    explicit_stop = False
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)

    async def send_results() -> None:
        nonlocal first_result_at
        while True:
            event = await session.next_event()
            if event is None:
                return
            if first_result_at is None and event.get("type") == "transcript":
                first_result_at = time.monotonic()
            safe_event = {
                key: value
                for key, value in event.items()
                if key != "request_id"
            }
            await websocket.send_json(safe_event)

    async def send_audio() -> None:
        while True:
            data = await audio_queue.get()
            if data is None:
                return
            await session.send_audio(data)

    result_task = asyncio.create_task(send_results())
    audio_task = asyncio.create_task(send_audio())
    stop_started_at = time.monotonic()
    try:
        while True:
            try:
                message = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                break
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                data = message["bytes"]
                packet_count += 1
                audio_bytes += len(data)
                try:
                    audio_queue.put_nowait(data)
                except asyncio.QueueFull:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "AUDIO_BACKPRESSURE",
                            "message": "网络或语音服务积压过高，请检查已有文字后重试",
                            "retryable": True,
                        }
                    )
                    break
                queue_peak = max(queue_peak, audio_queue.qsize())
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
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "PROTOCOL_ERROR",
                    "message": "录音消息顺序无效",
                    "retryable": False,
                }
            )
            break
    finally:
        stop_started_at = time.monotonic()
        await audio_queue.put(None)
        try:
            await audio_task
        finally:
            try:
                await session.stop()
            finally:
                await result_task

    if not explicit_stop:
        return

    duration_ms = audio_bytes * 1000 // (16000 * 2)
    await websocket.send_json(
        {
            "type": "done",
            "session_id": session_id,
            "duration_ms": duration_ms,
        }
    )
    logger.info(
        "ASR session complete session_id=%s model=%s packets=%d "
        "audio_ms=%d queue_peak=%d first_result_ms=%s stop_done_ms=%d",
        session_id,
        settings.realtime_model,
        packet_count,
        duration_ms,
        queue_peak,
        (
            round((first_result_at - started_at) * 1000)
            if first_result_at is not None
            else None
        ),
        round((time.monotonic() - stop_started_at) * 1000),
    )


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
