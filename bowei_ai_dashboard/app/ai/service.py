"""Policy-based AI invocation with encrypted credentials and sanitized auditing."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services.realtime_asr import AsrStartError
from app.settings import AsrSettings

from .adapters import DefaultAIAdapters
from .contracts import (
    AICapabilityNotConfigured,
    AIInvocationContext,
    AIUpstreamError,
    Capability,
    ModelType,
)
from .crypto import AICredentialCipher, AIConfigurationKeyError


RESPONSE_VALIDATION_ERROR_CODES = frozenset({
    "json_missing_or_multiple",
    "json_malformed",
    "schema_invalid",
})


_SAFE_ERROR_CODES = {
    *RESPONSE_VALIDATION_ERROR_CODES,
    "AI_RESPONSE_INVALID",
    "AI_UPSTREAM_TIMEOUT",
    "AI_UPSTREAM_RATE_LIMIT",
    "AI_UPSTREAM_5XX",
    "AI_UPSTREAM_CONNECTION",
    "AI_UPSTREAM_BAD_REQUEST",
    "AI_UPSTREAM_AUTH",
    "AI_UPSTREAM_UNKNOWN",
}


def sanitize_invocation_error_code(error_code: str) -> str:
    return error_code if not error_code or error_code in _SAFE_ERROR_CODES else "AI_UPSTREAM_UNKNOWN"


@dataclass(frozen=True)
class ChatResult:
    text: str
    model_code: str
    invocation_log_id: int


@dataclass(frozen=True)
class ASRResult:
    text: str
    model_code: str
    invocation_log_id: int


class RealtimeASRHandle:
    """Starts one selected ASR session and only retries before audio is accepted."""

    def __init__(self, service: "AIService", candidates: list[models.AIModel], policy, settings, context_text, context):
        self._service = service
        self._candidates = candidates
        self._policy = policy
        self._settings = settings
        self._context_text = context_text
        self._context = context
        self._session: Any | None = None
        self.model_code = ""
        self.invocation_log_id: int | None = None

    def update_context(self, context_text: str) -> None:
        """Accept validated stream context until the upstream session starts."""
        if self._session is not None:
            raise RuntimeError("ASR session context cannot change after start")
        self._context_text = context_text

    async def start(self) -> None:
        last_error: AIUpstreamError | None = None
        for attempt_no, model in enumerate(self._candidates, start=1):
            started = time.monotonic()
            try:
                api_key = self._service._credential(model.id)
                session = self._service.adapters.create_realtime_asr_session(
                    model, api_key, settings=self._settings, context=self._context_text
                )
                await session.start()
            except Exception as exc:
                error = self._service._to_upstream_error(exc)
                self._service._log(
                    self._policy,
                    model,
                    attempt_no,
                    "failed",
                    attempt_no > 1,
                    int((time.monotonic() - started) * 1000),
                    error.code,
                    self._context,
                )
                self._service.db.commit()
                last_error = error
                if not error.retryable:
                    raise error from exc
                continue
            log = self._service._log(
                self._policy,
                model,
                attempt_no,
                "succeeded",
                attempt_no > 1,
                int((time.monotonic() - started) * 1000),
                "",
                self._context,
            )
            self._service.db.commit()
            self._session = session
            self.model_code = model.code
            self.invocation_log_id = log.id
            return
        raise last_error or AICapabilityNotConfigured("AI capability has no usable model")

    async def send_audio(self, frame: bytes) -> None:
        if self._session is None:
            raise RuntimeError("ASR session has not started")
        await self._session.send_audio(frame)

    async def next_event(self):
        if self._session is None:
            raise RuntimeError("ASR session has not started")
        return await self._session.next_event()

    async def stop(self) -> None:
        if self._session is not None:
            await self._session.stop()


class AIService:
    def __init__(
        self,
        db: Session,
        *,
        adapters: Any | None = None,
        cipher_key: str | None = None,
    ) -> None:
        self.db = db
        self.adapters = adapters or DefaultAIAdapters()
        self._cipher = AICredentialCipher(
            cipher_key if cipher_key is not None else os.getenv("AI_CONFIG_ENCRYPTION_KEY", "")
        )

    def _candidates(self, capability_key: str, model_type: ModelType):
        try:
            Capability.required_model_type(capability_key)
        except ValueError as exc:
            raise AICapabilityNotConfigured(str(exc)) from exc
        policy = (
            self.db.query(models.AICapabilityPolicy)
            .filter_by(capability_key=capability_key, enabled=True)
            .one_or_none()
        )
        if policy is None or policy.primary_model_id is None:
            raise AICapabilityNotConfigured("AI capability is not configured")
        try:
            fallback_ids = json.loads(policy.fallback_model_ids_json or "[]")
        except json.JSONDecodeError as exc:
            raise AICapabilityNotConfigured("AI capability fallback policy is invalid") from exc
        model_ids = [policy.primary_model_id, *fallback_ids][: policy.max_attempts]
        candidates: list[models.AIModel] = []
        for model_id in model_ids:
            model = self.db.get(models.AIModel, model_id)
            if model is None or not model.enabled or model.model_type != model_type.value:
                raise AICapabilityNotConfigured("AI capability model is not eligible")
            candidates.append(model)
        if not candidates:
            raise AICapabilityNotConfigured("AI capability has no usable model")
        return policy, candidates

    def _credential(self, model_id: int) -> str:
        credential = (
            self.db.query(models.AIModelCredential).filter_by(model_id=model_id).one_or_none()
        )
        if credential is None or not credential.encrypted_api_key:
            raise AICapabilityNotConfigured("AI model credential is not configured")
        try:
            return self._cipher.decrypt(credential.encrypted_api_key)
        except AIConfigurationKeyError as exc:
            raise AICapabilityNotConfigured("AI model credential cannot be read") from exc

    @staticmethod
    def _to_upstream_error(exc: Exception) -> AIUpstreamError:
        if isinstance(exc, AIUpstreamError):
            return exc
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return AIUpstreamError("AI_UPSTREAM_TIMEOUT", retryable=True)
        if isinstance(exc, (ConnectionError, OSError, AsrStartError)):
            return AIUpstreamError("AI_UPSTREAM_CONNECTION", retryable=True)
        return AIUpstreamError("AI_UPSTREAM_UNKNOWN", retryable=False)

    def _log(
        self,
        policy: models.AICapabilityPolicy,
        model: models.AIModel,
        attempt_no: int,
        status: str,
        fallback_used: bool,
        duration_ms: int,
        error_code: str,
        context: AIInvocationContext,
    ) -> models.AIInvocationLog:
        log = models.AIInvocationLog(
            capability_key=policy.capability_key,
            policy_version=policy.policy_version,
            model_id=model.id,
            model_revision=model.revision,
            attempt_no=attempt_no,
            status=status,
            fallback_used=fallback_used,
            duration_ms=max(0, duration_ms),
            error_code=sanitize_invocation_error_code(error_code),
            resource_type=context.resource_type,
            resource_id=context.resource_id,
            actor=context.actor,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def _invoke(
        self,
        capability_key: str,
        model_type: ModelType,
        context: AIInvocationContext | None,
        invoke,
    ) -> tuple[str, models.AIModel, models.AIInvocationLog]:
        policy, candidates = self._candidates(capability_key, model_type)
        return self._invoke_candidates(policy, candidates, context, invoke)

    def _invoke_candidates(
        self,
        policy: models.AICapabilityPolicy,
        candidates: list[models.AIModel],
        context: AIInvocationContext | None,
        invoke,
    ) -> tuple[str, models.AIModel, models.AIInvocationLog]:
        invocation_context = context or AIInvocationContext()
        last_error: AIUpstreamError | None = None
        for attempt_no, model in enumerate(candidates, start=1):
            started = time.monotonic()
            fallback_used = model.id != policy.primary_model_id
            try:
                timeout_seconds = (
                    policy.fallback_timeout_seconds
                    if fallback_used
                    else policy.timeout_seconds
                )
                result = invoke(model, self._credential(model.id), timeout_seconds)
            except Exception as exc:
                error = self._to_upstream_error(exc)
                self._log(
                    policy,
                    model,
                    attempt_no,
                    "failed",
                    fallback_used,
                    int((time.monotonic() - started) * 1000),
                    error.code,
                    invocation_context,
                )
                # Release SQLite's write lock before contacting the next
                # provider. A model request can take tens of seconds.
                self.db.commit()
                last_error = error
                if not error.retryable:
                    raise error from exc
                continue
            log = self._log(
                policy,
                model,
                attempt_no,
                "succeeded",
                fallback_used,
                int((time.monotonic() - started) * 1000),
                "",
                invocation_context,
            )
            self.db.commit()
            return result, model, log
        raise last_error or AICapabilityNotConfigured("AI capability has no usable model")

    @staticmethod
    def _project_init_vision_enabled(model: models.AIModel) -> bool:
        if model.provider != "deepseek":
            return False
        try:
            config = json.loads(model.config_json or "{}")
        except json.JSONDecodeError:
            return False
        return isinstance(config, dict) and (
            config.get("vision_project_init_analysis") is True
            or config.get("vision_workbook_analysis") is True
        )

    def invoke_chat(
        self,
        capability_key: str,
        prompt: str,
        context: AIInvocationContext | None = None,
        response_validator: Callable[[str], bool | str | None] | None = None,
    ) -> ChatResult:
        text, model, log = self._invoke(
            capability_key,
            ModelType.CHAT,
            context,
            lambda current, api_key, timeout: self._complete_validated_chat(
                current,
                api_key,
                prompt,
                None if capability_key == Capability.TASK_PLAN_PROPOSAL else timeout,
                response_validator,
                {"type": "json_object"} if capability_key == Capability.PROJECT_INIT_ANALYSIS else None,
            ),
        )
        return ChatResult(text=text, model_code=model.code, invocation_log_id=log.id)

    def _complete_validated_chat(
        self,
        model: models.AIModel,
        api_key: str,
        prompt: str,
        timeout_seconds: int,
        response_validator: Callable[[str], bool | str | None] | None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        options = {"response_format": response_format} if response_format is not None else {}
        text = self.adapters.complete_chat(
            model,
            api_key,
            prompt,
            timeout_seconds=timeout_seconds,
            **options,
        )
        if response_validator is not None:
            validation = response_validator(text)
            # Legacy validators return bool; classifiers return None or a safe code.
            if validation is not None and validation is not True:
                code = validation if isinstance(validation, str) and validation in RESPONSE_VALIDATION_ERROR_CODES else "AI_RESPONSE_INVALID"
                raise AIUpstreamError(code, retryable=True)
        return text

    def invoke_project_init_vision(
        self,
        images: list[Path],
        prompt: str,
        context: AIInvocationContext | None = None,
    ) -> ChatResult:
        policy, candidates = self._candidates(
            Capability.PROJECT_INIT_ANALYSIS,
            ModelType.CHAT,
        )
        vision_candidates = [
            model for model in candidates if self._project_init_vision_enabled(model)
        ]
        if not vision_candidates:
            raise AICapabilityNotConfigured(
                "project init vision has no explicitly opted-in model"
            )
        text, model, log = self._invoke_candidates(
            policy,
            vision_candidates,
            context,
            lambda current, api_key, timeout: self.adapters.complete_project_init_vision(
                current,
                api_key,
                images,
                prompt,
                timeout_seconds=timeout,
            ),
        )
        return ChatResult(text=text, model_code=model.code, invocation_log_id=log.id)

    def transcribe_file(
        self,
        capability_key: str,
        content: bytes,
        filename: str,
        context: AIInvocationContext | None = None,
    ) -> ASRResult:
        text, model, log = self._invoke(
            capability_key,
            ModelType.ASR,
            context,
            lambda current, api_key, timeout: self.adapters.transcribe_file(
                current, api_key, content, filename, timeout_seconds=timeout
            ),
        )
        return ASRResult(text=text, model_code=model.code, invocation_log_id=log.id)

    def create_realtime_asr_session(
        self,
        capability_key: str,
        *,
        settings: AsrSettings,
        context_text: str,
        context: AIInvocationContext | None = None,
    ) -> RealtimeASRHandle:
        policy, candidates = self._candidates(capability_key, ModelType.ASR)
        return RealtimeASRHandle(
            self,
            candidates,
            policy,
            settings,
            context_text,
            context or AIInvocationContext(),
        )
