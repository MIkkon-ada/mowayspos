"""Evidence-bound project-init drafts produced from rendered workbook images."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..ai.contracts import AIInvocationContext
from ..ai.service import AIService, ChatResult
from .project_init_ai_agent import ProjectInitAiResult, generate_project_init_draft
from .project_init_file_parser import SourceChunk


def generate_project_init_vision_draft(
    images: list[Path],
    chunks: Iterable[SourceChunk | dict[str, Any]],
    existing_people: Iterable[dict[str, Any]],
    existing_tasks: Iterable[dict[str, Any]],
    *,
    ai_service: AIService,
    invocation_context: AIInvocationContext | None = None,
) -> ProjectInitAiResult:
    """Invoke vision while retaining the standard draft and evidence contract."""

    calls: list[ChatResult] = []

    def vision_call(prompt: str) -> str:
        result = ai_service.invoke_project_init_vision(
            images,
            prompt,
            invocation_context or AIInvocationContext(resource_type="project_init"),
        )
        calls.append(result)
        return result.text

    draft = generate_project_init_draft(
        chunks,
        existing_people,
        existing_tasks,
        llm_call=vision_call,
    )
    if not calls:
        return draft
    return draft.model_copy(
        update={
            "provider": "deepseek-vision",
            "model_name": calls[-1].model_code,
        }
    )
