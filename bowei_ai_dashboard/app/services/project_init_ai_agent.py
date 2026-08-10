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
from difflib import SequenceMatcher
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..llm_config import get_provider_config, resolve_provider
from .project_init_file_parser import SourceChunk

MAX_BATCH_CHARS = 40_000
LLM_TIMEOUT_SECONDS = 90
_POSITIVE_ID = Annotated[int, Field(strict=True, gt=0)]
_POSITIVE_ID_ADAPTER = TypeAdapter(_POSITIVE_ID)
_MERGE_STATUSES = Literal["new", "definite_duplicate", "possible_duplicate"]


class ProjectInitAiError(RuntimeError):
    """Safe business error for unavailable or invalid AI draft results."""


class ProjectInitAiEmptyResult(ProjectInitAiError):
    """The model returned a valid envelope without any usable tasks."""


class AgentWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=300)
    person_name: str = Field(default="", max_length=50)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    attachment_id: _POSITIVE_ID
    file_name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=300)

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
    deadline: str = Field(default="", max_length=50)
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
    deadline: str = Field(default="", max_length=50)
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
    return re.sub(r"[\W_]+", "", str(value or "").casefold())


def _normalise_title(value: object) -> str:
    return _normalise_name(value)


def _person_candidates(values: Iterable[PersonCandidate | dict[str, Any]]) -> list[PersonCandidate]:
    result: list[PersonCandidate] = []
    seen_ids: set[int] = set()
    for value in values:
        try:
            person = value if isinstance(value, PersonCandidate) else PersonCandidate.model_validate(value)
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
        "unmatched_person": "未找到可自动绑定的人员，保留原始姓名",
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
    return None, [_warning("unmatched_person", clean_name)]


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = _normalise_name(text)
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _dedupe_warnings(values: Iterable[AgentWarning]) -> list[AgentWarning]:
    result: list[AgentWarning] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (value.code, value.person_name)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _source_parts(value: SourceChunk | dict[str, Any]) -> tuple[str, str, str, int | None]:
    if isinstance(value, SourceChunk):
        return value.file_name, value.location, value.text, None
    if isinstance(value, tuple) and len(value) == 4:
        return value
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
        and raw.excerpt in source[2]
        and (source[3] is None or source[3] == raw.attachment_id)
    ]
    if not matches:
        raise ProjectInitAiError(f"AI 返回了无法追溯的来源：{raw.file_name} · {raw.location}")
    source = matches[0]
    return Evidence(
        attachment_id=raw.attachment_id,
        file_name=source[0],
        location=source[1],
        excerpt=raw.excerpt,
    )


def _safe_evidence_list(values: list[Evidence], sources: list[tuple[str, str, str, int | None]]) -> list[Evidence]:
    if not sources:
        return values
    return [_safe_evidence(value, sources) for value in values]


def _existing_task_index(existing_tasks: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    subtasks: list[dict[str, Any]] = []
    seen_task_ids: set[int] = set()
    for item in existing_tasks:
        if not isinstance(item, dict):
            raise ProjectInitAiError("现有任务上下文格式无效")
        task_id = item.get("id")
        if task_id is not None:
            if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
                raise ProjectInitAiError("现有任务包含非法 ID")
            if task_id in seen_task_ids:
                continue
            seen_task_ids.add(task_id)
        tasks.append(item)
        for subtask in item.get("subtasks") or []:
            if isinstance(subtask, dict):
                subtasks.append({**subtask, "parent_id": task_id})
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
    owner_id, owner_warnings = _match_person(task.owner_name, people)
    task.evidence = _safe_evidence_list(task.evidence, sources)
    if task.evidence and not task.source:
        task.source = task.evidence[0].source_label
    merge_status, duplicate_of, duplicate_reason = _classify_duplicate(task.title, existing_tasks)
    reconciled_subtasks: list[AgentSubTask] = []
    for subtask in task.subtasks:
        assignee_id, assignee_warnings = _match_person(subtask.assignee_name, people)
        helper_ids: list[int] = []
        helper_warnings: list[AgentWarning] = []
        for helper_name in _dedupe_strings(subtask.helper_names):
            helper_id, warnings = _match_person(helper_name, people)
            if helper_id is not None and helper_id not in helper_ids:
                helper_ids.append(helper_id)
            helper_warnings.extend(warnings)
        subtask.evidence = _safe_evidence_list(subtask.evidence or task.evidence, sources)
        if subtask.evidence and not subtask.source:
            subtask.source = subtask.evidence[0].source_label
        sub_merge, sub_duplicate_of, sub_duplicate_reason = _classify_duplicate(subtask.title, existing_subtasks)
        subtask.assignee_id = assignee_id
        subtask.helper_ids = helper_ids
        subtask.merge_status = sub_merge
        subtask.duplicate_of = sub_duplicate_of
        subtask.duplicate_reason = sub_duplicate_reason
        subtask.warnings = _dedupe_warnings(
            [*subtask.warnings, *assignee_warnings, *helper_warnings]
        )
        reconciled_subtasks.append(subtask)
    task.owner_id = owner_id
    task.merge_status = merge_status
    task.duplicate_of = duplicate_of
    task.duplicate_reason = duplicate_reason
    task.warnings = _dedupe_warnings([*task.warnings, *owner_warnings])
    task.subtasks = reconciled_subtasks
    return task


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
        {"source_label": f"{file_name} · {location}", "text": text}
        for file_name, location, text, _ in batch
    ]
    people_context = [person.model_dump() for person in people]
    return (
        "你是项目初始化工作推进表草稿提取 Agent。只返回 JSON 对象，结构必须是 {\"tasks\": [...] }。"
        "不要输出 Markdown、解释文字或代码围栏。"
        "不执行数据库、项目或成员修改；不得发明人员、日期或人员 ID。"
        "所有任务和子任务必须来自来源文本，并保留 evidence 的 attachment_id、file_name、location、excerpt。"
        "人员姓名只作为待匹配文本，服务端会重新匹配人员 ID；不要自动合并已有任务。"
        f"\n本地预计算人员候选：{json.dumps(people_context, ensure_ascii=False)}"
        f"\n本地已有任务重复索引：{json.dumps(existing_tasks, ensure_ascii=False)}"
        f"\n本批来源（总文本不超过 {MAX_BATCH_CHARS} 字符）：{json.dumps(sources, ensure_ascii=False)}"
    )


def _parse_json_response(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ProjectInitAiError("AI 返回格式无效")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ProjectInitAiError("AI 返回的 Markdown JSON 围栏无效")
        text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ProjectInitAiError("AI 未返回严格 JSON") from exc
    if not isinstance(value, dict):
        raise ProjectInitAiError("AI 返回的 JSON 根节点必须是对象")
    return value


def _validate_batch_sources(tasks: Iterable[AgentTask], batch: list[tuple[str, str, str, int | None]]) -> None:
    """Fail closed if one batch cites a file/location from another batch."""
    for task in tasks:
        task_evidence = task.evidence
        if not task_evidence and task.subtasks:
            task_evidence = task.subtasks[0].evidence
        if not task_evidence:
            raise ProjectInitAiError("AI 任务缺少来源证据")
        _safe_evidence_list(task_evidence, batch)
        for subtask in task.subtasks:
            _safe_evidence_list(subtask.evidence or task_evidence, batch)


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


def _default_llm_call(prompt: str, provider: str) -> str:
    config = get_provider_config(provider)
    if not config.get("api_key"):
        raise ProjectInitAiError(f"AI 引擎（{provider}）未配置 API Key")
    try:
        if provider == "anthropic":
            import anthropic

            response = anthropic.Anthropic(
                api_key=config["api_key"],
                timeout=LLM_TIMEOUT_SECONDS,
            ).messages.create(
                model=config["model"],
                max_tokens=6_000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        from openai import OpenAI

        response = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=LLM_TIMEOUT_SECONDS,
        ).chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=6_000,
        )
        return response.choices[0].message.content or ""
    except ProjectInitAiError:
        raise
    except Exception as exc:
        raise ProjectInitAiError(f"AI 引擎（{provider}）调用失败") from exc


def generate_project_init_draft(
    chunks: Iterable[SourceChunk | dict[str, Any]],
    existing_people: Iterable[PersonCandidate | dict[str, Any]],
    existing_tasks: Iterable[dict[str, Any]],
    llm_call: Callable[..., Any] | None = None,
) -> ProjectInitAiResult:
    """Extract and reconcile a review-only project-init draft without DB writes."""
    source_values = _source_index(chunks)
    if not source_values:
        raise ProjectInitAiEmptyResult("没有可分析的来源片段")
    people = _person_candidates(existing_people)
    indexed_tasks, _ = _existing_task_index(existing_tasks)
    provider = resolve_provider() if llm_call is None else "injected"
    caller = llm_call or _default_llm_call
    all_tasks: list[dict[str, Any]] = []
    for batch in _split_batches(source_values):
        prompt = _context_prompt(batch, people, indexed_tasks)
        try:
            raw = _invoke_llm(caller, prompt, provider)
            payload = _parse_json_response(raw)
            envelope = _RawEnvelope.model_validate(payload)
        except ProjectInitAiError:
            raise
        except ValidationError as exc:
            raise ProjectInitAiError("AI 草稿结构或字段类型无效") from exc
        except Exception as exc:
            raise ProjectInitAiError("AI 草稿处理失败") from exc
        _validate_batch_sources(envelope.tasks, batch)
        all_tasks.extend(task.model_dump() for task in envelope.tasks)
    if not all_tasks:
        raise ProjectInitAiEmptyResult("AI 未提取到可用任务")
    result = normalize_agent_result(
        {"tasks": all_tasks},
        people,
        existing_tasks=indexed_tasks,
        chunks=source_values,
        provider=provider,
        model_name=get_provider_config(provider).get("model", "") if provider != "injected" else "",
    )
    return result
