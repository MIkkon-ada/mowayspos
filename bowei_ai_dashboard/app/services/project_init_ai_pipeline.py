"""Model-call orchestration for project-init AI draft suggestions."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable, Iterable
from typing import Any

from pydantic import ValidationError

from ..ai.contracts import AIInvocationContext, AIUpstreamError, Capability
from ..ai.service import AIService
from .project_init_ai_contracts import (
    AgentTask,
    AgentWarning,
    Evidence,
    PersonCandidate,
    ProjectInitAiEmptyResult,
    ProjectInitAiError,
    ProjectInitAiInvalidDraft,
    ProjectInitAiResult,
    ProjectProfileDraft,
    _RawEnvelope,
    _safe_validation_errors,
)
from .project_init_ai_normalization import (
    _existing_task_index,
    _merge_project_profiles,
    _merge_tasks,
    _person_candidates,
    _reconcile_project_profile,
    _source_index,
    _source_label,
    has_cross_batch_task_conflict,
    normalize_agent_result,
)
from .project_init_ai_spreadsheet import (
    _evidence_traceability_error,
    _repair_batch_evidence,
    _structured_spreadsheet_fallback,
)
from .project_init_file_parser import SourceChunk

MAX_BATCH_CHARS = 40_000

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
        "你是项目立项资料草稿提取 Agent。只返回 JSON 对象，结构必须是 {\"project_profile\": {...}, \"tasks\": [...] }。"
        "不要输出 Markdown、解释文字或代码围栏。"
        "不执行数据库、项目或成员修改；不得发明人员、日期或人员 ID。"
        "所有任务和子任务必须来自来源文本，并提供 evidence 的 attachment_id、file_name、location 定位器。"
        "Evidence 必须引用本批来源目录；attachment_id、file_name、location 必须完全一致。"
        "来源目录中的 attachment_id 为 null 时，evidence 的 attachment_id 必须为 null，禁止伪造非空 ID。"
        "日期字段使用 plan_start、plan_end，不使用 deadline；只有开始月份时，plan_start 写 YYYY-MM-01，plan_end 置为空字符串，不能把开始月份写入 plan_end。"
        "父任务 description 是历史兼容字段，优先复制 goal；不得重复第一个 subtask 的 title。"
        "请先按语义把内容分为项目基本信息和工作推进方案，不要要求固定表头或固定字体。项目名称、建设背景、立项原因、项目目标、预期成果、项目周期、项目说明分别映射到 project_profile 的 name、background、objectives、expected_outcomes、start_date、end_date、description；主要工作/专项映射到 task title；目标、目标成果映射到 task goal；验收标准、关键成果、验收标准与关键成果映射到 task acceptance_criteria；推进流程、实施流程、流程映射到 task process；关键任务映射到 subtasks。兼容旧字段：关键成果或完成标准映射到父任务 description。"
        "如果一个单元格包含 1.、2.、3. 等编号条目，请拆成多个 subtasks 或 acceptance_criteria 条目，不要把整格当成一个任务标题；保留未知列的有效信息到最接近的 description、subtask description 或 evidence 中。"
        "输出字段必须严格遵循：project_profile 只能包含 name、background、objectives、expected_outcomes、start_date、end_date、description、evidence；task 只能包含 title、description、goal、acceptance_criteria、process、owner_name、priority、status、plan_start、plan_end、evidence、subtasks；"
        "subtask 只能包含 title、description、assignee_name、helper_names、priority、status、plan_start、plan_end、evaluation_standard、evidence。"
        "evidence 只能包含 attachment_id、file_name、location；不要输出 excerpt 或 source_label，服务端会生成真实摘录。"
        "不要输出 source、任何人员 ID、confidence、merge_status、duplicate_of、duplicate_reason 或 warnings；这些字段由服务端统一计算。"
        "project_profile 只要有任一非空字段就必须包含至少一个 evidence；每个 task 必须至少包含一个 subtasks 项；未知或空缺的可选字符串字段使用空字符串，不要使用 null。"
        "人员姓名只作为待匹配文本，服务端会重新匹配人员 ID；不要自动合并已有任务。"
        f"\n本地预计算人员候选：{json.dumps(people_context, ensure_ascii=False)}"
        f"\n本地已有任务重复索引：{json.dumps(existing_tasks, ensure_ascii=False)}"
        f"\n本批来源（总文本不超过 {MAX_BATCH_CHARS} 字符）：{json.dumps(sources, ensure_ascii=False)}"
    )


def _semantic_workbook_batch(batch: list[tuple[str, str, str, int | None]]) -> bool:
    """Detect a semantic table without requiring one exact header vocabulary."""
    markers = ("目标", "验收", "关键成果", "推进流程", "实施流程", "主要工作")
    return any(
        "\t" in text
        and any(marker in text.splitlines()[0] for marker in markers)
        for _file_name, _location, text, _attachment_id in batch
    )


def _requires_semantic_ai_route(
    sources: list[tuple[str, str, str, int | None]],
) -> bool:
    """Keep explicit semantic tables on the AI route before deterministic repair."""
    for _file_name, _location, text, _attachment_id in sources:
        if "\t" not in text or not text.splitlines():
            continue
        header_line = text.splitlines()[0]
        # Legacy work-plan tables also contain columns such as “目标” and
        # “评价标准”. Route the newer semantic layout to AI only when its
        # distinctive work/process headers are present together.
        if "主要工作" in header_line and (
            "推进流程" in header_line
            or "实施流程" in header_line
            or "验收标准与关键成果" in header_line
        ):
            return True
    return False


def _missing_semantic_fields(tasks: Iterable[AgentTask]) -> set[str]:
    missing: set[str] = set()
    for task in tasks:
        for field_name in ("goal", "acceptance_criteria", "process"):
            if not getattr(task, field_name).strip():
                missing.add(field_name)
    return missing


def _semantic_repair_prompt(
    batch: list[tuple[str, str, str, int | None]],
    tasks: list[AgentTask],
    missing_fields: set[str],
) -> str:
    sources = [
        {
            "attachment_id": attachment_id,
            "file_name": file_name,
            "location": location,
            "text": text,
        }
        for file_name, location, text, attachment_id in batch
    ]
    return (
        "你是项目初始化工作推进表的语义字段修复 Agent。只返回严格 JSON 对象，结构必须是 {\"tasks\": [...]}。"
        "下面的候选已经完成任务和子任务识别，请只根据来源补齐缺失的语义字段，不要改动任务标题、子任务标题、人员、日期或 evidence。"
        "目标字段：goal=目标/预期结果，acceptance_criteria=验收标准/关键成果，process=推进流程/实施流程。"
        "如果来源对应字段确实为空，使用空字符串；禁止臆造。每个 task 仍须包含至少一个 subtasks 项。"
        "不要输出来源目录之外的 evidence，不要输出任何服务端计算字段。"
        f"\n只需修复这些字段：{json.dumps(sorted(missing_fields), ensure_ascii=False)}"
        f"\n已有候选：{json.dumps([task.model_dump(mode='python') for task in tasks], ensure_ascii=False)}"
        f"\n来源表格：{json.dumps(sources, ensure_ascii=False)}"
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
        "父任务 description 是历史兼容字段，优先复制 goal；不得重复第一个 subtask 的 title。"
        "来源内容层级映射：专项映射到 task title；目标映射到 goal；验收标准或关键成果映射到 acceptance_criteria；推进流程映射到 process；关键任务映射到 subtasks。兼容旧字段：关键成果或完成标准映射到父任务 description。"
        "evidence 只能包含 attachment_id、file_name、location；不要输出 excerpt 或 source_label，服务端会生成真实摘录。每个 task 必须至少包含一个 subtasks 项；可选字符串为空时使用空字符串，不要使用 null。"
        "不要输出 source、任何人员 ID、confidence、merge_status、duplicate_of、duplicate_reason 或 warnings；这些字段由服务端统一计算。"
        f"\n候选任务：{json.dumps([task.model_dump() for task in tasks], ensure_ascii=False)}"
        f"\n允许的来源目录：{json.dumps(source_catalog, ensure_ascii=False)}"
    )


_TASK_OPTIONAL_TEXT_FIELDS = {
    "description",
    "goal",
    "acceptance_criteria",
    "process",
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
    "goal": 2_000,
    "acceptance_criteria": 2_000,
    "process": 2_000,
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


_PROJECT_PROFILE_SERVER_OWNED_FIELDS = {"confidence", "warnings"}
_PROJECT_PROFILE_TEXT_FIELD_LIMITS = {
    "name": 100,
    "background": 10_000,
    "objectives": 10_000,
    "expected_outcomes": 10_000,
    "start_date": 20,
    "end_date": 20,
    "description": 10_000,
}


def _normalise_project_profile_payload(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for key in _PROJECT_PROFILE_SERVER_OWNED_FIELDS:
        result.pop(key, None)
    for key, limit in _PROJECT_PROFILE_TEXT_FIELD_LIMITS.items():
        if result.get(key) is None:
            result[key] = ""
        elif isinstance(result.get(key), str):
            result[key] = result[key][:limit]
    if isinstance(result.get("evidence"), list):
        result["evidence"] = [_normalise_evidence_payload(item) for item in result["evidence"]]
    return result


def _normalise_llm_payload(value: object) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    if isinstance(result.get("project_profile"), dict):
        result["project_profile"] = _normalise_project_profile_payload(result["project_profile"])
    if isinstance(result.get("tasks"), list):
        result["tasks"] = [_normalise_task_payload(item) for item in result["tasks"]]
    return result


class _JsonResponseError(ProjectInitAiError):
    def __init__(self, code: str) -> None:
        super().__init__("AI 返回的 JSON 不唯一或无法解析")
        self.code = code


def _parse_json_response(raw: str | dict[str, Any]) -> Any:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise _JsonResponseError("json_missing_or_multiple")
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
                    except ValueError:
                        # Includes malformed JSON and decoder integer-size limits.
                        raise _JsonResponseError("json_malformed") from None
                    cursor = index + 1
                    found_end = True
                    break
        if not found_end:
            raise _JsonResponseError("json_malformed")
    if len(values) != 1:
        raise _JsonResponseError("json_missing_or_multiple")
    return values[0]


def _classify_raw_draft_envelope(raw: str) -> str | None:
    try:
        payload = _parse_json_response(raw)
        _RawEnvelope.model_validate(_normalise_llm_payload(payload))
    except _JsonResponseError as exc:
        return exc.code
    except ValidationError:
        return "schema_invalid"
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


def _validate_batch_sources(
    tasks: Iterable[AgentTask],
    batch: list[tuple[str, str, str, int | None]],
    project_profile: ProjectProfileDraft | None = None,
) -> None:
    """Fail closed if one batch cites a file/location from another batch."""
    if project_profile is not None and project_profile.has_content():
        if not project_profile.evidence:
            raise ProjectInitAiInvalidDraft(
                "AI 项目基本信息缺少来源证据",
                validation_errors=[{"path": "project_profile.evidence", "type": "missing_evidence"}],
            )
        _validate_evidence_group(
            project_profile.evidence,
            path="project_profile.evidence",
            batch=batch,
        )
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
    structured_draft = None
    if not _requires_semantic_ai_route(source_values):
        structured_draft = _structured_spreadsheet_fallback(
            source_values,
            people,
            indexed_tasks,
            "local-rule",
            model_name="structured-spreadsheet",
            require_full_coverage=True,
        )
    if structured_draft is not None:
        return structured_draft
    if llm_call is not None:
        provider = "injected"
        caller = llm_call
    elif ai_service is not None:
        provider = Capability.PROJECT_INIT_ANALYSIS
        caller = lambda prompt: ai_service.invoke_chat(
            Capability.PROJECT_INIT_ANALYSIS,
            prompt,
            invocation_context or AIInvocationContext(resource_type="project_init"),
            response_validator=_classify_raw_draft_envelope,
        ).text
    else:
        raise ProjectInitAiError("AI capability service is required")
    batches = _split_batches(source_values)
    canonical_sources = [source for batch in batches for source in batch]
    all_tasks: list[AgentTask] = []
    batch_tasks: list[list[AgentTask]] = []
    all_profiles: list[ProjectProfileDraft] = []
    for batch in batches:
        prompt = _context_prompt(batch, people, indexed_tasks)
        try:
            raw = _invoke_llm(caller, prompt, provider)
            payload = _parse_json_response(raw)
            envelope = _RawEnvelope.model_validate(_normalise_llm_payload(payload))
        except (ProjectInitAiError, AIUpstreamError):
            fallback = _structured_spreadsheet_fallback(
                canonical_sources,
                people,
                indexed_tasks,
                provider,
            )
            if fallback is not None:
                return fallback
            raise
        except ValidationError as exc:
            raise ProjectInitAiInvalidDraft(
                "AI 草稿结构或字段类型无效",
                validation_errors=_safe_validation_errors(exc),
            ) from exc
        except Exception as exc:
            raise ProjectInitAiError("AI 草稿处理失败") from exc
        envelope.project_profile = _reconcile_project_profile(envelope.project_profile, batch)
        missing_fields = _missing_semantic_fields(envelope.tasks) if _semantic_workbook_batch(batch) else set()
        if missing_fields:
            try:
                repair_raw = _invoke_llm(
                    caller,
                    _semantic_repair_prompt(batch, envelope.tasks, missing_fields),
                    provider,
                )
                repair_payload = _parse_json_response(repair_raw)
                repair_envelope = _RawEnvelope.model_validate(_normalise_llm_payload(repair_payload))
                envelope.tasks = _merge_tasks([*envelope.tasks, *repair_envelope.tasks])
            except Exception:
                # Optional AI repair must not discard a valid, evidence-bound draft.
                pass
            source_repair = _structured_spreadsheet_fallback(
                batch,
                people,
                indexed_tasks,
                provider,
                model_name="semantic-source-repair",
            )
            if source_repair is not None:
                envelope.tasks = _merge_tasks([*envelope.tasks, *source_repair.tasks])
            remaining_missing_fields = _missing_semantic_fields(envelope.tasks)
            if remaining_missing_fields:
                # The warning is surfaced to the reviewer instead of hiding the gap.
                for task in envelope.tasks:
                    task.warnings.append(
                        AgentWarning(
                            code="missing_source_field",
                            message=f"AI 未能补齐语义字段：{'、'.join(sorted(remaining_missing_fields))}，请人工核对来源。",
                        )
                    )
        envelope.tasks = [_repair_batch_evidence(task, batch) for task in envelope.tasks]
        try:
            _validate_batch_sources(envelope.tasks, batch, envelope.project_profile)
        except ProjectInitAiInvalidDraft:
            fallback = _structured_spreadsheet_fallback(
                canonical_sources,
                people,
                indexed_tasks,
                provider,
            )
            if fallback is not None:
                return fallback
            raise
        all_profiles.append(envelope.project_profile)
        batch_tasks.append(envelope.tasks)
        all_tasks = _merge_tasks([*all_tasks, *_merge_tasks(envelope.tasks)])
    merged_profile = _merge_project_profiles(all_profiles)
    if not all_tasks and not merged_profile.has_content():
        raise ProjectInitAiEmptyResult("AI 未提取到可用项目基本信息或任务")
    if has_cross_batch_task_conflict(batch_tasks):
        try:
            merge_raw = _invoke_llm(caller, _final_merge_prompt(all_tasks, canonical_sources), provider)
            merge_payload = _parse_json_response(merge_raw)
            merge_envelope = _RawEnvelope.model_validate(_normalise_llm_payload(merge_payload))
            merge_envelope.tasks = [
                _repair_batch_evidence(task, canonical_sources)
                for task in merge_envelope.tasks
            ]
            try:
                _validate_batch_sources(merge_envelope.tasks, canonical_sources)
            except ProjectInitAiInvalidDraft:
                fallback = _structured_spreadsheet_fallback(
                    canonical_sources,
                    people,
                    indexed_tasks,
                    provider,
                )
                if fallback is not None:
                    return fallback
                raise
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
    try:
        return normalize_agent_result(
            {
                "project_profile": merged_profile.model_dump(),
                "tasks": [task.model_dump() for task in all_tasks],
            },
            people,
            existing_tasks=indexed_tasks,
            chunks=canonical_sources,
            provider=provider,
            model_name="",
        )
    except ProjectInitAiError:
        fallback = _structured_spreadsheet_fallback(
            canonical_sources,
            people,
            indexed_tasks,
            provider,
        )
        if fallback is not None:
            return fallback
        raise
