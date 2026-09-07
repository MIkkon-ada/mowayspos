"""Provider SDK adapters used exclusively by the AI capability service."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from app import models
from app.ai.contracts import AIUpstreamError, classify_retryable_error
from app.services.realtime_asr import DashScopeRealtimeAsr
from app.settings import AsrSettings


class ChatAdapter(Protocol):
    def complete(
        self,
        model: models.AIModel,
        api_key: str,
        prompt: str,
        *,
        timeout_seconds: int,
        response_format: dict[str, str] | None = None,
    ) -> str: ...


class FileASRAdapter(Protocol):
    def transcribe(
        self,
        model: models.AIModel,
        api_key: str,
        content: bytes,
        filename: str,
        *,
        timeout_seconds: int,
    ) -> str: ...


class RealtimeASRAdapter(Protocol):
    def create_session(
        self,
        model: models.AIModel,
        api_key: str,
        *,
        settings: AsrSettings,
        context: str,
    ) -> DashScopeRealtimeAsr: ...


def _upstream_error(exc: Exception, *, status_code: int | None = None) -> AIUpstreamError:
    status = status_code if status_code is not None else getattr(exc, "status_code", None)
    if isinstance(exc, TimeoutError) or status == 408:
        code = "AI_UPSTREAM_TIMEOUT"
    elif status == 429:
        code = "AI_UPSTREAM_RATE_LIMIT"
    elif isinstance(status, int) and 500 <= status <= 599:
        code = "AI_UPSTREAM_5XX"
    elif status in {400, 404, 409, 422}:
        code = "AI_UPSTREAM_BAD_REQUEST"
    elif status in {401, 403}:
        code = "AI_UPSTREAM_AUTH"
    elif isinstance(exc, (ConnectionError, OSError)):
        code = "AI_UPSTREAM_CONNECTION"
    else:
        code = "AI_UPSTREAM_UNKNOWN"
    return AIUpstreamError(code, retryable=classify_retryable_error(status_code=status))


class OpenAICompatibleChatAdapter:
    def complete(
        self,
        model: models.AIModel,
        api_key: str,
        prompt: str,
        *,
        timeout_seconds: int,
        response_format: dict[str, str] | None = None,
    ) -> str:
        try:
            from openai import APIConnectionError, APITimeoutError, OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=model.base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
            request = {
                "model": model.model_name,
                "messages": [{"role": "user", "content": prompt}],
            }
            try:
                config = json.loads(model.config_json or "{}")
            except json.JSONDecodeError:
                config = {}
            max_output_tokens = config.get("max_output_tokens") if isinstance(config, dict) else None
            if isinstance(max_output_tokens, int) and not isinstance(max_output_tokens, bool) and max_output_tokens > 0:
                request["max_tokens"] = max_output_tokens
            if response_format is None:
                response_format = config.get("response_format") if isinstance(config, dict) else None
            if response_format == {"type": "json_object"}:
                request["response_format"] = response_format
            response = client.chat.completions.create(**request)
            return str(response.choices[0].message.content or "")
        except APITimeoutError as exc:
            raise AIUpstreamError("AI_UPSTREAM_TIMEOUT", retryable=True) from exc
        except APIConnectionError as exc:
            raise AIUpstreamError("AI_UPSTREAM_CONNECTION", retryable=True) from exc
        except AIUpstreamError:
            raise
        except Exception as exc:
            raise _upstream_error(exc) from exc

    def complete_images(
        self,
        model: models.AIModel,
        api_key: str,
        images: list[Path],
        prompt: str,
        *,
        timeout_seconds: int,
    ) -> str:
        try:
            from openai import APIConnectionError, APITimeoutError, OpenAI

            config = _model_config(model)
            if model.provider != "deepseek" or config.get("vision_workbook_analysis") is not True:
                raise AIUpstreamError("AI_UPSTREAM_BAD_REQUEST", retryable=False)
            if not images or any(Path(image).suffix.lower() != ".png" for image in images):
                raise AIUpstreamError("AI_UPSTREAM_BAD_REQUEST", retryable=False)
            client = OpenAI(
                api_key=api_key,
                base_url=f"{model.base_url.rstrip('/')}/beta",
                timeout=timeout_seconds,
                max_retries=0,
            )
            content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
            for image in images:
                content.append(
                    {
                        "type": "file",
                        "file_data": "data:image/png;base64,"
                        + base64.b64encode(Path(image).read_bytes()).decode("ascii"),
                        "filename": Path(image).name,
                    }
                )
            request: dict[str, object] = {
                "model": str(config.get("vision_model") or "deepseek-v4-flash-vision-exp"),
                "messages": [{"role": "user", "content": content}],
            }
            if config.get("response_format") == {"type": "json_object"}:
                request["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**request)
            return str(response.choices[0].message.content or "")
        except APITimeoutError as exc:
            raise AIUpstreamError("AI_UPSTREAM_TIMEOUT", retryable=True) from exc
        except APIConnectionError as exc:
            raise AIUpstreamError("AI_UPSTREAM_CONNECTION", retryable=True) from exc
        except AIUpstreamError:
            raise
        except Exception as exc:
            raise _upstream_error(exc) from exc


def _model_config(model: models.AIModel) -> dict[str, Any]:
    try:
        config = json.loads(model.config_json or "{}")
    except json.JSONDecodeError:
        return {}
    return config if isinstance(config, dict) else {}


class AnthropicChatAdapter:
    def complete(
        self,
        model: models.AIModel,
        api_key: str,
        prompt: str,
        *,
        timeout_seconds: int,
        response_format: dict[str, str] | None = None,
    ) -> str:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key, base_url=model.base_url, timeout=timeout_seconds)
            messages = [{"role": "user", "content": prompt}]
            json_object = response_format == {"type": "json_object"}
            if json_object:
                messages[0]["content"] += "\nReturn exactly one JSON object and no other text."
                messages.append({"role": "assistant", "content": "{"})
            response = client.messages.create(
                model=model.model_name,
                max_tokens=4096,
                messages=messages,
            )
            return ("{" if json_object else "") + "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
        except AIUpstreamError:
            raise
        except Exception as exc:
            raise _upstream_error(exc) from exc


class DashScopeFileASRAdapter:
    @staticmethod
    def _format(filename: str) -> str:
        extension = os.path.splitext(filename)[1].lower()
        return {
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
        }.get(extension, "mp3")

    def transcribe(
        self,
        model: models.AIModel,
        api_key: str,
        content: bytes,
        filename: str,
        *,
        timeout_seconds: int,
    ) -> str:
        suffix = os.path.splitext(filename)[1].lower() or ".mp3"
        tmp_path = ""
        try:
            from dashscope.audio.asr import Recognition

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(content)
                tmp_path = handle.name
            try:
                config = json.loads(model.config_json or "{}")
            except json.JSONDecodeError:
                config = {}
            recognition = Recognition(
                model=config.get("file_model", "paraformer-realtime-v2"),
                format=self._format(filename),
                sample_rate=16000,
                language_hints=["zh", "en"],
                api_key=api_key,
                callback=None,
            )
            result = recognition.call(tmp_path)
            if result.status_code != 200:
                raise _upstream_error(
                    RuntimeError("ASR provider rejected request"),
                    status_code=result.status_code,
                )
            output = result.output or {}
            sentences = output.get("sentence") or []
            if sentences:
                return "".join(
                    sentence.get("text", "") for sentence in sentences if sentence.get("text")
                )
            return str(output.get("text", ""))
        except AIUpstreamError:
            raise
        except Exception as exc:
            raise _upstream_error(exc) from exc
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


class DashScopeRealtimeASRAdapter:
    def create_session(
        self,
        model: models.AIModel,
        api_key: str,
        *,
        settings: AsrSettings,
        context: str,
    ) -> DashScopeRealtimeAsr:
        try:
            config = json.loads(model.config_json or "{}")
        except json.JSONDecodeError:
            config = {}
        return DashScopeRealtimeAsr(
            api_key,
            replace(
                settings,
                realtime_model=str(config.get("realtime_model") or settings.realtime_model),
            ),
            context,
        )


class DefaultAIAdapters:
    """Dispatch model/provider calls without exposing SDK clients to services."""

    def __init__(self) -> None:
        self._openai = OpenAICompatibleChatAdapter()
        self._anthropic = AnthropicChatAdapter()
        self._file_asr = DashScopeFileASRAdapter()
        self._realtime_asr = DashScopeRealtimeASRAdapter()

    def complete_chat(
        self,
        model: models.AIModel,
        api_key: str,
        prompt: str,
        *,
        timeout_seconds: int,
        response_format: dict[str, str] | None = None,
    ) -> str:
        options = {"response_format": response_format} if response_format is not None else {}
        if model.provider == "anthropic":
            return self._anthropic.complete(model, api_key, prompt, timeout_seconds=timeout_seconds, **options)
        if model.provider in {"deepseek", "dashscope", "glm"}:
            return self._openai.complete(model, api_key, prompt, timeout_seconds=timeout_seconds, **options)
        raise AIUpstreamError("AI_UPSTREAM_UNKNOWN", retryable=False)

    def transcribe_file(
        self,
        model: models.AIModel,
        api_key: str,
        content: bytes,
        filename: str,
        *,
        timeout_seconds: int,
    ) -> str:
        if model.provider != "dashscope":
            raise AIUpstreamError("AI_UPSTREAM_UNKNOWN", retryable=False)
        return self._file_asr.transcribe(
            model, api_key, content, filename, timeout_seconds=timeout_seconds
        )

    def complete_project_init_vision(
        self,
        model: models.AIModel,
        api_key: str,
        images: list[Path],
        prompt: str,
        *,
        timeout_seconds: int,
    ) -> str:
        if model.provider != "deepseek":
            raise AIUpstreamError("AI_UPSTREAM_UNKNOWN", retryable=False)
        return self._openai.complete_images(
            model, api_key, images, prompt, timeout_seconds=timeout_seconds
        )

    def create_realtime_asr_session(
        self,
        model: models.AIModel,
        api_key: str,
        *,
        settings: AsrSettings,
        context: str,
    ) -> DashScopeRealtimeAsr:
        if model.provider != "dashscope":
            raise AIUpstreamError("AI_UPSTREAM_UNKNOWN", retryable=False)
        return self._realtime_asr.create_session(
            model, api_key, settings=settings, context=context
        )
