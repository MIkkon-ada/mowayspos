"""Audio transcription via Dashscope Paraformer."""

from __future__ import annotations

import asyncio
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, WebSocket
from fastapi.websockets import WebSocketDisconnect

from ..llm_config import get_provider_config
from ..permissions import get_current_user_name
from ..auth import get_session_user
from ..settings import get_settings

router = APIRouter(prefix="/api/transcribe", tags=["transcribe"])

_SUPPORTED_FORMATS = {
    ".mp3", ".mp4", ".wav", ".flac", ".aac", ".ogg",
    ".m4a", ".wma", ".amr", ".webm",
}


def _detect_format(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    fmt_map = {
        ".mp3": "mp3", ".wav": "wav", ".flac": "flac",
        ".aac": "aac", ".ogg": "ogg-opus", ".m4a": "m4a",
        ".wma": "wma", ".amr": "amr", ".webm": "opus",
        ".mp4": "mp4",
    }
    return fmt_map.get(ext, "mp3")


def _do_transcribe(file_bytes: bytes, filename: str, api_key: str) -> str:
    from dashscope.audio.asr import Recognition  # noqa: PLC0415
    import dashscope

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
            raise RuntimeError(f"转写失败（{result.status_code}）: {result.message}")

        output = result.output or {}
        sentences = output.get("sentence") or []
        if sentences:
            text = "".join(s.get("text", "") for s in sentences if s.get("text"))
            return text  # 可能是空字符串（静音），正常返回
        text = output.get("text", "")
        return text  # 空字符串表示静音，交给前端处理
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
        raise HTTPException(500, "未配置 Dashscope API Key，请在系统设置中填写")

    content = await file.read()
    if len(content) > 200 * 1024 * 1024:  # 200 MB limit
        raise HTTPException(413, "文件过大，最大支持 200MB")

    try:
        text = await asyncio.to_thread(_do_transcribe, content, filename, api_key)
        return {"text": text, "filename": filename}
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.websocket("/stream")
async def transcribe_stream(websocket: WebSocket):
    """实时流式 ASR。前端以 PCM 16kHz Int16 帧流式发送，后端实时推送句子识别结果。

    消息协议：
    - 客户端 → 服务端：binary（PCM 帧） 或 text "stop"（结束录音）
    - 服务端 → 客户端：JSON {"text": str, "final": bool} 或 {"error": str}
    """
    session_id = websocket.cookies.get(get_settings().session_cookie_name)
    username = get_session_user(session_id) if session_id else None
    if not username:
        await websocket.close(code=4001, reason="未登录")
        return

    api_key = get_provider_config("dashscope").get("api_key", "")
    if not api_key:
        await websocket.close(code=4002, reason="未配置 Dashscope API Key")
        return

    await websocket.accept()

    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _on_result(result, *args, **kwargs):
        if result.status_code == 200:
            sentence = (result.output or {}).get("sentence") or {}
            text = (sentence.get("text") or "").strip()
            if text:
                asyncio.run_coroutine_threadsafe(
                    q.put({"text": text, "final": bool(sentence.get("sentence_end", False))}),
                    loop,
                )

    import dashscope  # noqa: PLC0415
    from dashscope.audio.asr import Recognition  # noqa: PLC0415

    dashscope.api_key = api_key
    rec = Recognition(
        model="paraformer-realtime-v2",
        format="pcm",
        sample_rate=16000,
        language_hints=["zh", "en"],
        callback=_on_result,
    )
    await asyncio.to_thread(rec.start)

    async def _sender():
        while True:
            item = await q.get()
            if item is None:
                break
            try:
                await websocket.send_json(item)
            except Exception:
                break

    sender = asyncio.create_task(_sender())

    try:
        while True:
            try:
                msg = await websocket.receive()
            except (WebSocketDisconnect, Exception):
                break
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await asyncio.to_thread(rec.send_audio_frame, msg["bytes"])
            elif msg.get("text") == "stop":
                break
    finally:
        await asyncio.to_thread(rec.stop)
        await asyncio.sleep(0.8)  # 等待最后一批回调触发
        await q.put(None)
        await sender
        try:
            await websocket.close()
        except Exception:
            pass
