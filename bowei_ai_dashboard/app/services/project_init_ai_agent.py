"""Pure, review-only AI drafting for project-init source material.

The service deliberately keeps all persistence and project/member mutations out of
the pipeline. Model output is an untrusted suggestion: IDs, ownership matches,
source evidence, and duplicate classifications are validated or recomputed here.
"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable, Iterable
from datetime import date
from difflib import SequenceMatcher
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..ai.contracts import AIInvocationContext, Capability
from ..ai.service import AIService
from .project_init_file_parser import SourceChunk

MAX_BATCH_CHARS = 40_000
LLM_TIMEOUT_SECONDS = 90
_POSITIVE_ID = Annotated[int, Field(strict=True, gt=0)]
_POSITIVE_ID_ADAPTER = TypeAdapter(_POSITIVE_ID)
_MERGE_STATUSES = Literal["new", "definite_duplicate", "possible_duplicate"]
_YEAR_MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")
_ISO_DATE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])")


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
    "tasks",
    "subtasks",
    "title",
    "description",
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


class ProjectInitAiResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tasks: list[AgentTask] = Field(min_length=1, max_length=100)
    provider: str = ""
    model_name: str = ""


class _RawEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tasks: list[AgentTask] = Field(default_factory=list, max_length=100)


def _normalise_name(value: object) -> str:
    return str(value or "").strip().casefold()


def _normalise_title(value: object) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").strip().casefold())


def _is_calendar_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _normalise_start_only_dates(payload: dict[str, Any]) -> None:
    """Move a valid end-only date into the start field for imported work plans."""
    plan_start = str(payload.get("plan_start") or "")
    plan_end = str(payload.get("plan_end") or "")
    if plan_start:
        return
    if _YEAR_MONTH.fullmatch(plan_end):
        payload["plan_start"] = f"{plan_end}-01"
        payload["plan_end"] = ""
    elif _ISO_DATE.fullmatch(plan_end) and _is_calendar_date(plan_end):
        payload["plan_start"] = plan_end
        payload["plan_end"] = ""


def _source_label(file_name: str, location: str) -> str:
    return Evidence(file_name=file_name, location=location, excerpt="source").source_label


def _person_candidates(values: Iterable[PersonCandidate | dict[str, Any]]) -> list[PersonCandidate]:
    result: list[PersonCandidate] = []
    seen_ids: set[int] = set()
    for value in values:
        try:
            person = value if isinstance(value, PersonCandidate) else PersonCandidate.model_validate(
                {
                    "id": value.get("id"),
                    "name": value.get("name"),
                    "is_active": value.get("is_active", True),
                }
            )
        except ValidationError as exc:
            raise ProjectInitAiError("人员候选包含非法 ID 或字段") from exc
        if person.id in seen_ids:
            continue
        seen_ids.add(person.id)
        result.append(person)
    return result


def _warning(code: str, person_name: str) -> AgentWarning:
    messages = {
        "ambiguous_person": "存在多个同名在职人员，未自动绑定",
        "inactive_person": "仅找到停用人员，未自动绑定",
        "person_not_found": "未找到可自动绑定的人员，保留原始姓名",
        "helper_conflicts_with_owner": "负责人不能同时作为协助人，已移除重复协助人",
        "helper_conflicts_with_assignee": "关键任务负责人不能同时作为协助人，已移除重复协助人",
    }
    return AgentWarning(code=code, message=messages.get(code, code), person_name=person_name)


def _match_person(name: str, people: list[PersonCandidate]) -> tuple[int | None, list[AgentWarning]]:
    clean_name = str(name or "").strip()
    if not clean_name:
        return None, []
    matches = [person for person in people if _normalise_name(person.name) == _normalise_name(clean_name)]
    active = [person for person in matches if person.is_active]
    if len(active) == 1:
        return active[0].id, []
    if len(active) > 1:
        return None, [_warning("ambiguous_person", clean_name)]
    if matches:
        return None, [_warning("inactive_person", clean_name)]
    return None, [_warning("person_not_found", clean_name)]


def _dedupe_strings(values: Iterable[str], *, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = _normalise_name(text)
        if text and key not in seen:
            seen.add(key)
            if len(result) >= limit:
                break
            result.append(text)
    return result


def _dedupe_warnings(values: Iterable[AgentWarning], *, limit: int = 20) -> list[AgentWarning]:
    result: list[AgentWarning] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (value.code, value.person_name)
        if key not in seen:
            seen.add(key)
            if len(result) >= limit:
                break
            result.append(value)
    return result


def _dedupe_evidence(values: Iterable[Evidence], *, limit: int = 10) -> list[Evidence]:
    result: list[Evidence] = []
    seen: set[tuple[int | None, str, str, str]] = set()
    for value in values:
        key = (value.attachment_id, value.file_name, value.location, value.excerpt)
        if key not in seen:
            seen.add(key)
            if len(result) >= limit:
                break
            result.append(value)
    return result


def _merge_non_empty(left: str, right: str) -> str:
    return left or right


def _merge_subtask_values(left: AgentSubTask, right: AgentSubTask) -> AgentSubTask:
    merged = left.model_dump(mode="python")
    for field_name in (
        "description",
        "assignee_name",
        "priority",
        "status",
        "plan_start",
        "plan_end",
        "evaluation_standard",
        "source",
        "duplicate_reason",
    ):
        merged[field_name] = _merge_non_empty(merged[field_name], getattr(right, field_name))
    merged["confidence"] = max(merged["confidence"], right.confidence)
    merged["helper_names"] = _dedupe_strings([*merged["helper_names"], *right.helper_names])
    merged["helper_ids"] = list(dict.fromkeys([*merged["helper_ids"], *right.helper_ids]))[:20]
    merged["evidence"] = [item.model_dump(mode="python") for item in _dedupe_evidence(
        [*left.evidence, *right.evidence]
    )]
    merged["warnings"] = [item.model_dump(mode="python") for item in _dedupe_warnings(
        [*left.warnings, *right.warnings]
    )]
    return AgentSubTask.model_validate(merged)


def _merge_task_values(left: AgentTask, right: AgentTask) -> AgentTask:
    merged = left.model_dump(mode="python")
    for field_name in (
        "description",
        "owner_name",
        "priority",
        "status",
        "plan_start",
        "plan_end",
        "source",
        "duplicate_reason",
    ):
        merged[field_name] = _merge_non_empty(merged[field_name], getattr(right, field_name))
    merged["confidence"] = max(merged["confidence"], right.confidence)
    merged["evidence"] = [item.model_dump(mode="python") for item in _dedupe_evidence(
        [*left.evidence, *right.evidence]
    )]
    merged["warnings"] = [item.model_dump(mode="python") for item in _dedupe_warnings(
        [*left.warnings, *right.warnings]
    )]
    subtasks: dict[str, AgentSubTask] = {
        _normalise_title(item.title): item.model_copy(deep=True) for item in left.subtasks
    }
    for subtask in right.subtasks:
        key = _normalise_title(subtask.title)
        if key in subtasks:
            subtasks[key] = _merge_subtask_values(subtasks[key], subtask)
        else:
            subtasks[key] = subtask.model_copy(deep=True)
    merged["subtasks"] = [item.model_dump(mode="python") for item in list(subtasks.values())[:100]]
    return AgentTask.model_validate(merged)


def _merge_tasks(values: Iterable[AgentTask]) -> list[AgentTask]:
    merged: dict[str, AgentTask] = {}
    for task in values:
        task = AgentTask.model_validate(task)
        key = _normalise_title(task.title)
        if key in merged:
            merged[key] = _merge_task_values(merged[key], task)
        else:
            merged[key] = task.model_copy(deep=True)
        if len(merged) > 100:
            raise ProjectInitAiError("AI 返回的任务数量超过上限")
    return [AgentTask.model_validate(task.model_dump(mode="python")) for task in merged.values()]


def _source_parts(value: SourceChunk | dict[str, Any]) -> tuple[str, str, str, int | None]:
    if isinstance(value, SourceChunk):
        return value.file_name, value.location, value.text, None
    if isinstance(value, tuple) and len(value) == 4:
        file_name, location, text, attachment_id = value
        if attachment_id is not None:
            try:
                attachment_id = _POSITIVE_ID_ADAPTER.validate_python(attachment_id)
            except Exception as exc:
                raise ProjectInitAiError("来源片段包含非法附件 ID") from exc
        return str(file_name), str(location), str(text), attachment_id
    if not isinstance(value, dict):
        raise ProjectInitAiError("来源片段格式无效")
    try:
        file_name = str(value["file_name"])
        location = str(value["location"])
        text = str(value["text"])
    except (KeyError, TypeError) as exc:
        raise ProjectInitAiError("来源片段缺少文件名、位置或文本") from exc
    attachment_id = value.get("attachment_id")
    if attachment_id is not None:
        try:
            attachment_id = _POSITIVE_ID_ADAPTER.validate_python(attachment_id)
        except Exception as exc:
            raise ProjectInitAiError("来源片段包含非法附件 ID") from exc
    return file_name, location, text, attachment_id


def _source_index(chunks: Iterable[SourceChunk | dict[str, Any]]) -> list[tuple[str, str, str, int | None]]:
    result = []
    for value in chunks:
        file_name, location, text, attachment_id = _source_parts(value)
        if text:
            result.append((file_name, location, text, attachment_id))
    return result


def _safe_evidence(raw: Evidence, sources: list[tuple[str, str, str, int | None]]) -> Evidence:
    matches = [
        source
        for source in sources
        if source[0] == raw.file_name
        and source[1] == raw.location
        and source[3] == raw.attachment_id
    ]
    if not matches:
        raise ProjectInitAiError(f"AI 返回了无法追溯的来源：{raw.file_name} · {raw.location}")
    source = matches[0]
    return Evidence(
        attachment_id=raw.attachment_id,
        file_name=source[0],
        location=source[1],
        excerpt=source[2].strip()[:300],
    )


def _safe_evidence_list(values: list[Evidence], sources: list[tuple[str, str, str, int | None]]) -> list[Evidence]:
    if values and not sources:
        raise ProjectInitAiError("AI 返回了无法追溯的来源")
    return [_safe_evidence(value, sources) for value in values]


def _existing_task_index(existing_tasks: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    subtasks: list[dict[str, Any]] = []
    seen_task_ids: set[int] = set()
    seen_subtask_ids: set[int] = set()
    for item in existing_tasks:
        if not isinstance(item, dict):
            raise ProjectInitAiError("现有任务上下文格式无效")
        try:
            task_id = _POSITIVE_ID_ADAPTER.validate_python(item["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectInitAiError("现有任务包含非法 ID") from exc
        if task_id in seen_task_ids:
            raise ProjectInitAiError("现有任务包含重复 ID")
        seen_task_ids.add(task_id)
        task_copy = dict(item)
        task_copy["id"] = task_id
        raw_subtasks = task_copy.get("subtasks") or []
        if not isinstance(raw_subtasks, list):
            raise ProjectInitAiError("现有子任务上下文格式无效")
        normalized_subtasks: list[dict[str, Any]] = []
        for subtask in raw_subtasks:
            if not isinstance(subtask, dict):
                raise ProjectInitAiError("现有子任务上下文格式无效")
            try:
                subtask_id = _POSITIVE_ID_ADAPTER.validate_python(subtask["id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProjectInitAiError("现有子任务包含非法 ID") from exc
            if subtask_id in seen_subtask_ids:
                raise ProjectInitAiError("现有子任务包含重复 ID")
            seen_subtask_ids.add(subtask_id)
            subtask_copy = dict(subtask)
            subtask_copy["id"] = subtask_id
            normalized_subtasks.append(subtask_copy)
            subtasks.append({**subtask_copy, "parent_id": task_id})
        task_copy["subtasks"] = normalized_subtasks
        tasks.append(task_copy)
    return tasks, subtasks


def _classify_duplicate(title: str, candidates: Iterable[dict[str, Any]]) -> tuple[str, int | None, str]:
    normalised = _normalise_title(title)
    if not normalised:
        return "new", None, ""
    for item in candidates:
        candidate_title = _normalise_title(item.get("title"))
        if not candidate_title:
            continue
        candidate_id = item.get("id")
        if normalised == candidate_title:
            return "definite_duplicate", candidate_id, "标准化标题完全相同"
    best: tuple[float, int | None] = (0.0, None)
    for item in candidates:
        candidate_title = _normalise_title(item.get("title"))
        score = SequenceMatcher(None, normalised, candidate_title).ratio()
        if score > best[0]:
            best = (score, item.get("id"))
    if best[0] >= 0.86:
        return "possible_duplicate", best[1], f"标题相似度 {best[0]:.2f}"
    return "new", None, ""


def _reconcile_task(
    task: AgentTask,
    people: list[PersonCandidate],
    existing_tasks: list[dict[str, Any]],
    existing_subtasks: list[dict[str, Any]],
    sources: list[tuple[str, str, str, int | None]],
) -> AgentTask:
    task = AgentTask.model_validate(task.model_dump(mode="python"))
    owner_id, owner_warnings = _match_person(task.owner_name, people)
    task_evidence = _safe_evidence_list(task.evidence, sources)
    task_source = task_evidence[0].source_label if task_evidence else task.source
    merge_status, duplicate_of, duplicate_reason = _classify_duplicate(task.title, existing_tasks)
    reconciled_subtasks: list[AgentSubTask] = []
    for subtask in task.subtasks:
        subtask = AgentSubTask.model_validate(subtask.model_dump(mode="python"))
        assignee_id, assignee_warnings = _match_person(subtask.assignee_name, people)
        helper_ids: list[int] = []
        helper_warnings: list[AgentWarning] = []
        for helper_name in _dedupe_strings(subtask.helper_names):
            helper_id, warnings = _match_person(helper_name, people)
            helper_warnings.extend(warnings)
            if helper_id is None:
                continue
            if helper_id == owner_id:
                helper_warnings.append(_warning("helper_conflicts_with_owner", helper_name.strip()))
                if helper_id == assignee_id:
                    helper_warnings.append(_warning("helper_conflicts_with_assignee", helper_name.strip()))
                continue
            if helper_id == assignee_id:
                helper_warnings.append(_warning("helper_conflicts_with_assignee", helper_name.strip()))
                continue
            if helper_id not in helper_ids:
                helper_ids.append(helper_id)
        subtask_evidence = _safe_evidence_list(subtask.evidence or task_evidence, sources)
        subtask_source = subtask_evidence[0].source_label if subtask_evidence else subtask.source
        sub_merge, sub_duplicate_of, sub_duplicate_reason = _classify_duplicate(subtask.title, existing_subtasks)
        subtask_data = subtask.model_dump(mode="python")
        _normalise_start_only_dates(subtask_data)
        subtask_data.update(
            {
                "assignee_id": assignee_id,
                "helper_ids": helper_ids[:20],
                "merge_status": sub_merge,
                "duplicate_of": sub_duplicate_of,
                "duplicate_reason": sub_duplicate_reason,
                "evidence": [item.model_dump(mode="python") for item in subtask_evidence[:10]],
                "source": subtask_source,
                "warnings": [
                    item.model_dump(mode="python")
                    for item in _dedupe_warnings([*subtask.warnings, *assignee_warnings, *helper_warnings])
                ],
            }
        )
        reconciled_subtasks.append(AgentSubTask.model_validate(subtask_data))
    task_data = task.model_dump(mode="python")
    _normalise_start_only_dates(task_data)
    if reconciled_subtasks and _normalise_title(task.description) == _normalise_title(reconciled_subtasks[0].title):
        task_data["description"] = ""
    if not task.description.strip():
        for subtask in reconciled_subtasks:
            evaluation_standard = subtask.evaluation_standard.strip()
            if evaluation_standard:
                task_data["description"] = evaluation_standard
                break
    task_data.update(
        {
            "owner_id": owner_id,
            "merge_status": merge_status,
            "duplicate_of": duplicate_of,
            "duplicate_reason": duplicate_reason,
            "evidence": [item.model_dump(mode="python") for item in task_evidence[:10]],
            "source": task_source,
            "warnings": [
                item.model_dump(mode="python") for item in _dedupe_warnings([*task.warnings, *owner_warnings])
            ],
            "subtasks": [item.model_dump(mode="python") for item in reconciled_subtasks[:100]],
        }
    )
    return AgentTask.model_validate(task_data)


def normalize_agent_result(
    raw_result: dict[str, Any],
    existing_people: Iterable[PersonCandidate | dict[str, Any]],
    existing_tasks: Iterable[dict[str, Any]] | None = None,
    current_draft: list[dict[str, Any]] | None = None,
    chunks: Iterable[SourceChunk | dict[str, Any]] | None = None,
    *,
    provider: str = "",
    model_name: str = "",
) -> ProjectInitAiResult:
    """Validate untrusted JSON and deterministically reconcile its suggestions."""
    del current_draft  # Deliberately read-only context; it is never mutated here.
    if not isinstance(raw_result, dict):
        raise ProjectInitAiError("AI 返回的不是 JSON 对象")
    try:
        envelope = _RawEnvelope.model_validate(raw_result)
    except ValidationError as exc:
        raise ProjectInitAiError("AI 草稿结构或字段类型无效") from exc
    if not envelope.tasks:
        raise ProjectInitAiEmptyResult("AI 未提取到可用任务")
    people = _person_candidates(existing_people)
    indexed_tasks, indexed_subtasks = _existing_task_index(existing_tasks or [])
    source_values = _source_index(chunks or [])
    tasks = [
        _reconcile_task(task, people, indexed_tasks, indexed_subtasks, source_values)
        for task in envelope.tasks
    ]
    return ProjectInitAiResult(tasks=tasks, provider=provider, model_name=model_name)


def _split_batches(chunks: list[tuple[str, str, str, int | None]]) -> list[list[tuple[str, str, str, int | None]]]:
    batches: list[list[tuple[str, str, str, int | None]]] = []
    current: list[tuple[str, str, str, int | None]] = []
    current_size = 0
    for file_name, location, text, attachment_id in chunks:
        remaining = text
        part = 1
        while remaining:
            room = MAX_BATCH_CHARS - current_size
            if room <= 0:
                batches.append(current)
                current = []
                current_size = 0
                room = MAX_BATCH_CHARS
            piece = remaining[:room]
            remaining = remaining[room:]
            piece_location = location if not text or len(text) <= MAX_BATCH_CHARS else f"{location} part {part}"
            current.append((file_name, piece_location, piece, attachment_id))
            current_size += len(piece)
            part += 1
            if current_size == MAX_BATCH_CHARS:
                batches.append(current)
                current = []
                current_size = 0
    if current:
        batches.append(current)
    return batches


def _context_prompt(
    batch: list[tuple[str, str, str, int | None]],
    people: list[PersonCandidate],
    existing_tasks: list[dict[str, Any]],
) -> str:
    sources = [
        {
            "attachment_id": attachment_id,
            "source_label": _source_label(file_name, location),
            "file_name": file_name,
            "location": location,
            "text": text,
        }
        for file_name, location, text, attachment_id in batch
    ]
    people_context = [person.model_dump() for person in people]
    return (
        "你是项目初始化工作推进表草稿提取 Agent。只返回 JSON 对象，结构必须是 {\"tasks\": [...] }。"
        "不要输出 Markdown、解释文字或代码围栏。"
        "不执行数据库、项目或成员修改；不得发明人员、日期或人员 ID。"
        "所有任务和子任务必须来自来源文本，并提供 evidence 的 attachment_id、file_name、location 定位器。"
        "Evidence 必须引用本批来源目录；attachment_id、file_name、location 必须完全一致。"
        "来源目录中的 attachment_id 为 null 时，evidence 的 attachment_id 必须为 null，禁止伪造非空 ID。"
        "日期字段使用 plan_start、plan_end，不使用 deadline；只有开始月份时，plan_start 写 YYYY-MM-01，plan_end 置为空字符串，不能把开始月份写入 plan_end。"
        "父任务 description 不得重复第一个 subtask 的 title；重复时使用空字符串。"
        "来源内容层级映射：专项映射到 task title；关键任务映射到 subtasks；关键成果或完成标准映射到父任务 description。"
        "输出字段必须严格遵循：task 只能包含 title、description、owner_name、priority、status、plan_start、plan_end、evidence、subtasks；"
        "subtask 只能包含 title、description、assignee_name、helper_names、priority、status、plan_start、plan_end、evaluation_standard、evidence。"
        "evidence 只能包含 attachment_id、file_name、location；不要输出 excerpt 或 source_label，服务端会生成真实摘录。"
        "不要输出 source、任何人员 ID、confidence、merge_status、duplicate_of、duplicate_reason 或 warnings；这些字段由服务端统一计算。"
        "每个 task 必须至少包含一个 subtasks 项；未知或空缺的可选字符串字段使用空字符串，不要使用 null。"
        "人员姓名只作为待匹配文本，服务端会重新匹配人员 ID；不要自动合并已有任务。"
        f"\n本地预计算人员候选：{json.dumps(people_context, ensure_ascii=False)}"
        f"\n本地已有任务重复索引：{json.dumps(existing_tasks, ensure_ascii=False)}"
        f"\n本批来源（总文本不超过 {MAX_BATCH_CHARS} 字符）：{json.dumps(sources, ensure_ascii=False)}"
    )


def _final_merge_prompt(
    tasks: list[AgentTask],
    sources: list[tuple[str, str, str, int | None]],
) -> str:
    source_catalog = [
        {
            "attachment_id": attachment_id,
            "source_label": _source_label(file_name, location),
            "file_name": file_name,
            "location": location,
            "excerpt": text[:300],
        }
        for file_name, location, text, attachment_id in sources
    ]
    return (
        "你是项目初始化工作推进表的最终合并 Agent。只返回严格 JSON 对象，结构必须是 {\"tasks\": [...] }。"
        "请将批次候选中归一化标题相同的任务合并为一条，保留全部 evidence 和 subtasks；"
        "不得发明任务、人员或来源，也不得删除唯一来源。每条 evidence 必须引用下方候选或来源目录中的真实 attachment_id、file_name、location；null attachment_id 不得改为非空。"
        "日期字段使用 plan_start、plan_end，不使用 deadline；只有开始月份时，plan_start 写 YYYY-MM-01，plan_end 置为空字符串，不能把开始月份写入 plan_end。"
        "父任务 description 不得重复第一个 subtask 的 title；重复时使用空字符串。"
        "来源内容层级映射：专项映射到 task title；关键任务映射到 subtasks；关键成果或完成标准映射到父任务 description。"
        "evidence 只能包含 attachment_id、file_name、location；不要输出 excerpt 或 source_label，服务端会生成真实摘录。每个 task 必须至少包含一个 subtasks 项；可选字符串为空时使用空字符串，不要使用 null。"
        "不要输出 source、任何人员 ID、confidence、merge_status、duplicate_of、duplicate_reason 或 warnings；这些字段由服务端统一计算。"
        f"\n候选任务：{json.dumps([task.model_dump() for task in tasks], ensure_ascii=False)}"
        f"\n允许的来源目录：{json.dumps(source_catalog, ensure_ascii=False)}"
    )


_TASK_OPTIONAL_TEXT_FIELDS = {
    "description",
    "owner_name",
    "priority",
    "status",
    "plan_start",
    "plan_end",
    "source",
}
_SUBTASK_OPTIONAL_TEXT_FIELDS = {
    "description",
    "assignee_name",
    "priority",
    "status",
    "plan_start",
    "plan_end",
    "evaluation_standard",
    "source",
}

_TASK_TEXT_FIELD_LIMITS = {
    "title": 200,
    "description": 2_000,
    "owner_name": 50,
    "priority": 30,
    "status": 50,
    "plan_start": 50,
    "plan_end": 50,
}
_SUBTASK_TEXT_FIELD_LIMITS = {
    "title": 200,
    "description": 2_000,
    "assignee_name": 50,
    "priority": 30,
    "status": 50,
    "plan_start": 50,
    "plan_end": 50,
    "evaluation_standard": 1_000,
}

_TASK_SERVER_OWNED_FIELDS = {
    "owner_id",
    "confidence",
    "merge_status",
    "duplicate_of",
    "duplicate_reason",
    "warnings",
    "source",
}
_SUBTASK_SERVER_OWNED_FIELDS = {
    "assignee_id",
    "helper_ids",
    "confidence",
    "merge_status",
    "duplicate_of",
    "duplicate_reason",
    "warnings",
    "source",
}


def _normalise_evidence_payload(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    result.pop("source_label", None)
    if isinstance(result.get("excerpt"), str):
        result["excerpt"] = result["excerpt"][:300]
    return result


def _normalise_task_payload(value: object, *, is_subtask: bool = False) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for key in _SUBTASK_SERVER_OWNED_FIELDS if is_subtask else _TASK_SERVER_OWNED_FIELDS:
        result.pop(key, None)
    for key, limit in (
        _SUBTASK_TEXT_FIELD_LIMITS if is_subtask else _TASK_TEXT_FIELD_LIMITS
    ).items():
        if isinstance(result.get(key), str):
            result[key] = result[key][:limit]
    if is_subtask and isinstance(result.get("helper_names"), str):
        result["helper_names"] = [
            name.strip()
            for name in re.split(r"[、,，;；\r\n]+", result["helper_names"])
            if name.strip()
        ]
    for key in _SUBTASK_OPTIONAL_TEXT_FIELDS if is_subtask else _TASK_OPTIONAL_TEXT_FIELDS:
        if result.get(key) is None:
            result[key] = ""
    if isinstance(result.get("evidence"), list):
        result["evidence"] = [_normalise_evidence_payload(item) for item in result["evidence"]]
    if not is_subtask and isinstance(result.get("subtasks"), list):
        result["subtasks"] = [
            _normalise_task_payload(item, is_subtask=True) for item in result["subtasks"]
        ]
    return result


def _normalise_llm_payload(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    if isinstance(result.get("tasks"), list):
        result["tasks"] = [_normalise_task_payload(item) for item in result["tasks"]]
    return result


def _parse_json_response(raw: str | dict[str, Any]) -> Any:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ProjectInitAiError("AI 返回格式无效")
    text = raw.strip()
    values: list[Any] = []
    cursor = 0
    while cursor < len(text):
        starts = [index for index in (text.find("{", cursor), text.find("[", cursor)) if index >= 0]
        if not starts:
            break
        start = min(starts)
        stack: list[str] = []
        in_string = False
        escaped = False
        found_end = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in "[{":
                stack.append(char)
            elif char in "]}":
                if not stack or (stack[-1], char) not in (("[", "]"), ("{", "}")):
                    break
                stack.pop()
                if not stack:
                    candidate = text[start : index + 1]
                    try:
                        values.append(json.loads(candidate))
                    except json.JSONDecodeError:
                        pass
                    cursor = index + 1
                    found_end = True
                    break
        if not found_end:
            cursor = start + 1
    if len(values) != 1:
        raise ProjectInitAiError("AI 返回的 JSON 不唯一或无法解析")
    return values[0]


def _evidence_traceability_error(raw: Evidence, sources: list[tuple[str, str, str, int | None]]) -> str | None:
    file_matches = [source for source in sources if source[0] == raw.file_name]
    if not file_matches:
        return "untraceable_file"
    location_matches = [source for source in file_matches if source[1] == raw.location]
    if not location_matches:
        return "untraceable_location"
    attachment_matches = [source for source in location_matches if source[3] == raw.attachment_id]
    if not attachment_matches:
        return "untraceable_attachment"
    return None


def _validate_evidence_group(
    evidence: list[Evidence],
    *,
    path: str,
    batch: list[tuple[str, str, str, int | None]],
) -> None:
    for index, item in enumerate(evidence):
        error_type = _evidence_traceability_error(item, batch)
        if error_type:
            raise ProjectInitAiInvalidDraft(
                "AI 返回了无法追溯的来源",
                validation_errors=[{"path": f"{path}[{index}]", "type": error_type}],
            )


def _validate_batch_sources(tasks: Iterable[AgentTask], batch: list[tuple[str, str, str, int | None]]) -> None:
    """Fail closed if one batch cites a file/location from another batch."""
    for task_index, task in enumerate(tasks):
        task_path = f"tasks[{task_index}]"
        if not task.evidence and not any(subtask.evidence for subtask in task.subtasks):
            raise ProjectInitAiInvalidDraft(
                "AI 任务缺少来源证据",
                validation_errors=[{"path": f"{task_path}.evidence", "type": "missing_evidence"}],
            )
        _validate_evidence_group(task.evidence, path=f"{task_path}.evidence", batch=batch)
        for subtask_index, subtask in enumerate(task.subtasks):
            if subtask.evidence:
                _validate_evidence_group(
                    subtask.evidence,
                    path=f"{task_path}.subtasks[{subtask_index}].evidence",
                    batch=batch,
                )


def _invoke_llm(llm_call: Callable[..., Any], prompt: str, provider: str) -> Any:
    try:
        signature = inspect.signature(llm_call)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
    except (TypeError, ValueError):
        positional = []
    if len(positional) <= 1:
        return llm_call(prompt)
    return llm_call(prompt, provider)


def generate_project_init_draft(
    chunks: Iterable[SourceChunk | dict[str, Any]],
    existing_people: Iterable[PersonCandidate | dict[str, Any]],
    existing_tasks: Iterable[dict[str, Any]],
    llm_call: Callable[..., Any] | None = None,
    ai_service: AIService | None = None,
    invocation_context: AIInvocationContext | None = None,
) -> ProjectInitAiResult:
    """Extract and reconcile a review-only project-init draft without DB writes."""
    source_values = _source_index(chunks)
    if not source_values:
        raise ProjectInitAiEmptyResult("没有可分析的来源片段")
    people = _person_candidates(existing_people)
    indexed_tasks, _ = _existing_task_index(existing_tasks)
    if llm_call is not None:
        provider = "injected"
        caller = llm_call
    elif ai_service is not None:
        provider = Capability.PROJECT_INIT_ANALYSIS
        caller = lambda prompt: ai_service.invoke_chat(
            Capability.PROJECT_INIT_ANALYSIS,
            prompt,
            invocation_context or AIInvocationContext(resource_type="project_init"),
        ).text
    else:
        raise ProjectInitAiError("AI capability service is required")
    batches = _split_batches(source_values)
    canonical_sources = [source for batch in batches for source in batch]
    all_tasks: list[AgentTask] = []
    for batch in batches:
        prompt = _context_prompt(batch, people, indexed_tasks)
        try:
            raw = _invoke_llm(caller, prompt, provider)
            payload = _parse_json_response(raw)
            envelope = _RawEnvelope.model_validate(_normalise_llm_payload(payload))
        except ProjectInitAiError:
            raise
        except ValidationError as exc:
            raise ProjectInitAiInvalidDraft(
                "AI 草稿结构或字段类型无效",
                validation_errors=_safe_validation_errors(exc),
            ) from exc
        except Exception as exc:
            raise ProjectInitAiError("AI 草稿处理失败") from exc
        _validate_batch_sources(envelope.tasks, batch)
        all_tasks = _merge_tasks([*all_tasks, *_merge_tasks(envelope.tasks)])
    if not all_tasks:
        raise ProjectInitAiEmptyResult("AI 未提取到可用任务")
    if len(batches) > 1:
        try:
            merge_raw = _invoke_llm(caller, _final_merge_prompt(all_tasks, canonical_sources), provider)
            merge_payload = _parse_json_response(merge_raw)
            merge_envelope = _RawEnvelope.model_validate(_normalise_llm_payload(merge_payload))
            _validate_batch_sources(merge_envelope.tasks, canonical_sources)
        except ProjectInitAiError:
            raise
        except ValidationError as exc:
            raise ProjectInitAiInvalidDraft(
                "AI 最终合并结构或字段类型无效",
                validation_errors=_safe_validation_errors(exc),
            ) from exc
        except Exception as exc:
            raise ProjectInitAiError("AI 最终合并处理失败") from exc
        all_tasks = _merge_tasks([*all_tasks, *_merge_tasks(merge_envelope.tasks)])
    result = normalize_agent_result(
        {"tasks": [task.model_dump() for task in all_tasks]},
        people,
        existing_tasks=indexed_tasks,
        chunks=canonical_sources,
        provider=provider,
        model_name="",
    )
    return result
