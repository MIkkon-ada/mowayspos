"""Stable contracts shared by AI configuration and runtime services."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ModelType(StrEnum):
    CHAT = "chat"
    ASR = "asr"


class Capability:
    MEETING_ANALYSIS = "meeting.analysis"
    TASK_EXTRACTION = "task.extraction"
    PROJECT_INIT_ANALYSIS = "project.init.analysis"
    SPEECH_REALTIME = "speech.realtime"

    _TYPES = {
        MEETING_ANALYSIS: ModelType.CHAT,
        TASK_EXTRACTION: ModelType.CHAT,
        PROJECT_INIT_ANALYSIS: ModelType.CHAT,
        SPEECH_REALTIME: ModelType.ASR,
    }

    @classmethod
    def required_model_type(cls, capability_key: str) -> ModelType:
        try:
            return cls._TYPES[capability_key]
        except KeyError as exc:
            raise ValueError(f"unsupported AI capability: {capability_key}") from exc


class AIServiceError(RuntimeError):
    code = "AI_SERVICE_ERROR"
    retryable = False


class AICapabilityNotConfigured(AIServiceError):
    code = "AI_CAPABILITY_NOT_CONFIGURED"


class AIUpstreamError(AIServiceError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        message: str = "AI upstream request failed",
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class AIInvocationContext:
    actor: str = ""
    resource_type: str = ""
    resource_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def classify_retryable_error(*, status_code: int | None) -> bool:
    """Return whether an upstream HTTP/network failure may be retried safely."""

    return status_code is None or status_code in {408, 429} or 500 <= status_code <= 599
