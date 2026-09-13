"""Validated contracts for project-init AI draft suggestions.

This module owns the untrusted-draft schema and safe error diagnostics. It has no
persistence, model-invocation, or facade dependency.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


_POSITIVE_ID = Annotated[int, Field(strict=True, gt=0)]
_POSITIVE_ID_ADAPTER = TypeAdapter(_POSITIVE_ID)
_MERGE_STATUSES = Literal["new", "definite_duplicate", "possible_duplicate"]

class ProjectInitAiError(RuntimeError):
    """Safe business error for unavailable or invalid AI draft results."""


class ProjectInitAiEmptyResult(ProjectInitAiError):
    """The model returned a valid envelope without any usable tasks."""


class ProjectInitAiInvalidDraft(ProjectInitAiError):
    """The model response was parseable but violated the draft contract."""

    def __init__(
        self,
        message: str,
        *,
        validation_errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors or []


_VALIDATION_PATH_SEGMENTS = {
    "project_profile",
    "tasks",
    "subtasks",
    "title",
    "description",
    "goal",
    "acceptance_criteria",
    "process",
    "owner_name",
    "owner_id",
    "assignee_name",
    "assignee_id",
    "helper_names",
    "helper_ids",
    "priority",
    "status",
    "plan_start",
    "plan_end",
    "evaluation_standard",
    "evidence",
    "attachment_id",
    "file_name",
    "location",
    "excerpt",
    "source",
    "confidence",
    "merge_status",
    "duplicate_of",
    "duplicate_reason",
    "warnings",
    "background",
    "objectives",
    "expected_outcomes",
    "start_date",
    "end_date",
}


def _safe_validation_errors(error: ValidationError) -> list[dict[str, str]]:
    """Expose bounded structural diagnostics without storing model input values."""
    diagnostics: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in error.errors()[:20]:
        location = item.get("loc")
        parts: list[str] = []
        for segment in location if isinstance(location, (list, tuple)) else ():
            if isinstance(segment, int):
                if parts:
                    parts[-1] = f"{parts[-1]}[{segment}]"
                else:
                    parts.append(f"[{segment}]")
            elif isinstance(segment, str) and segment in _VALIDATION_PATH_SEGMENTS:
                parts.append(segment)
            else:
                parts.append("<unexpected_field>")
        path = ".".join(parts) or "<invalid_location>"
        error_type = str(item.get("type") or "invalid")
        if not re.fullmatch(r"[a-z0-9_]+", error_type):
            error_type = "invalid"
        diagnostic = (path, error_type)
        if diagnostic not in seen:
            seen.add(diagnostic)
            diagnostics.append({"path": path, "type": error_type})
    return diagnostics


class AgentWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=300)
    person_name: str = Field(default="", max_length=50)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    attachment_id: _POSITIVE_ID | None = None
    file_name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(default="", max_length=300)

    @property
    def source_label(self) -> str:
        return f"{self.file_name} · {self.location}"


class PersonCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: _POSITIVE_ID
    name: str = Field(min_length=1, max_length=50)
    is_active: bool = True
    is_project_member: bool = True


class AgentSubTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    assignee_name: str = Field(default="", max_length=50)
    assignee_id: _POSITIVE_ID | None = None
    helper_names: list[str] = Field(default_factory=list, max_length=20)
    helper_ids: list[_POSITIVE_ID] = Field(default_factory=list, max_length=20)
    priority: str = Field(default="", max_length=30)
    status: str = Field(default="", max_length=50)
    plan_start: str = Field(default="", max_length=50)
    plan_end: str = Field(default="", max_length=50)
    evaluation_standard: str = Field(default="", max_length=1_000)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)
    source: str = Field(default="", max_length=255)
    merge_status: _MERGE_STATUSES = "new"
    duplicate_of: _POSITIVE_ID | None = None
    duplicate_reason: str = Field(default="", max_length=300)
    warnings: list[AgentWarning] = Field(default_factory=list, max_length=20)


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    goal: str = Field(default="", max_length=2_000)
    acceptance_criteria: str = Field(default="", max_length=2_000)
    process: str = Field(default="", max_length=2_000)
    owner_name: str = Field(default="", max_length=50)
    owner_id: _POSITIVE_ID | None = None
    priority: str = Field(default="", max_length=30)
    status: str = Field(default="", max_length=50)
    plan_start: str = Field(default="", max_length=50)
    plan_end: str = Field(default="", max_length=50)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)
    source: str = Field(default="", max_length=255)
    confidence: float = Field(default=0.0, ge=0, le=1)
    merge_status: _MERGE_STATUSES = "new"
    duplicate_of: _POSITIVE_ID | None = None
    duplicate_reason: str = Field(default="", max_length=300)
    warnings: list[AgentWarning] = Field(default_factory=list, max_length=20)
    subtasks: list[AgentSubTask] = Field(min_length=1, max_length=100)


class ProjectProfileDraft(BaseModel):
    """Evidence-bound project-level suggestions extracted from source files."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(default="", max_length=100)
    background: str = Field(default="", max_length=10_000)
    objectives: str = Field(default="", max_length=10_000)
    expected_outcomes: str = Field(default="", max_length=10_000)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=10_000)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    warnings: list[AgentWarning] = Field(default_factory=list, max_length=20)

    def has_content(self) -> bool:
        return any(
            getattr(self, field_name).strip()
            for field_name in (
                "name",
                "background",
                "objectives",
                "expected_outcomes",
                "start_date",
                "end_date",
                "description",
            )
        )


class ProjectInitAiResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_profile: ProjectProfileDraft = Field(default_factory=ProjectProfileDraft)
    tasks: list[AgentTask] = Field(default_factory=list, max_length=100)
    provider: str = ""
    model_name: str = ""


class _RawEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_profile: ProjectProfileDraft = Field(default_factory=ProjectProfileDraft)
    tasks: list[AgentTask] = Field(default_factory=list, max_length=100)
