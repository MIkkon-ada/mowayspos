"""Deterministic reconciliation for project-init AI draft suggestions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from pydantic import ValidationError

from .project_init_ai_contracts import (
    AgentSubTask,
    AgentTask,
    AgentWarning,
    Evidence,
    PersonCandidate,
    ProjectInitAiEmptyResult,
    ProjectInitAiError,
    ProjectInitAiInvalidDraft,
    ProjectInitAiResult,
    ProjectProfileDraft,
    _POSITIVE_ID_ADAPTER,
    _RawEnvelope,
)
from .project_init_file_parser import SourceChunk


_YEAR_MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")
_ISO_DATE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])")

def _normalise_name(value: object) -> str:
    return str(value or "").strip().casefold()


def _normalise_title(value: object) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").strip().casefold())


def has_cross_batch_task_conflict(batch_tasks: Iterable[Iterable[AgentTask]]) -> bool:
    """Detect plausible title duplicates across batches before local merging."""
    previous_titles: set[str] = set()
    for tasks in batch_tasks:
        titles = {_normalise_title(task.title) for task in tasks}
        for title in titles:
            if any(
                title == previous or SequenceMatcher(None, title, previous).ratio() >= 0.88
                for previous in previous_titles
            ):
                return True
        previous_titles.update(titles)
    return False


def _is_calendar_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _normalise_start_only_dates(payload: dict[str, Any]) -> None:
    """Normalize imported plan starts and move a valid end-only date into start."""
    plan_start = str(payload.get("plan_start") or "")
    plan_end = str(payload.get("plan_end") or "")
    if _YEAR_MONTH.fullmatch(plan_start):
        payload["plan_start"] = f"{plan_start}-01"
        return
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
                    "is_project_member": value.get("is_project_member", True),
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
        "will_join_project": "提交项目方案时将自动加入项目",
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
        person = active[0]
        return person.id, [] if person.is_project_member else [_warning("will_join_project", clean_name)]
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
        "goal",
        "acceptance_criteria",
        "process",
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


def _reconcile_project_profile(
    profile: ProjectProfileDraft,
    sources: list[tuple[str, str, str, int | None]],
) -> ProjectProfileDraft:
    """Keep project fields only when their source evidence is verifiable."""
    reconciled = profile.model_copy(deep=True)
    if not reconciled.has_content():
        reconciled.evidence = []
        reconciled.warnings = []
        return reconciled
    if not reconciled.evidence:
        raise ProjectInitAiInvalidDraft(
            "AI 项目基本信息缺少来源证据",
            validation_errors=[{"path": "project_profile.evidence", "type": "missing_evidence"}],
        )
    reconciled.evidence = _safe_evidence_list(reconciled.evidence, sources)
    for field_name in ("start_date", "end_date"):
        value = getattr(reconciled, field_name).strip()
        if value and (not _ISO_DATE.fullmatch(value) or not _is_calendar_date(value)):
            raise ProjectInitAiInvalidDraft(
                "AI 项目基本信息日期格式无效",
                validation_errors=[{"path": f"project_profile.{field_name}", "type": "invalid_date"}],
            )
    if reconciled.start_date and reconciled.end_date and reconciled.end_date < reconciled.start_date:
        raise ProjectInitAiInvalidDraft(
            "AI 项目基本信息结束日期早于开始日期",
            validation_errors=[{"path": "project_profile.end_date", "type": "invalid_date_range"}],
        )
    return reconciled


def _merge_project_profiles(values: Iterable[ProjectProfileDraft]) -> ProjectProfileDraft:
    merged = ProjectProfileDraft()
    for profile in values:
        candidate = ProjectProfileDraft.model_validate(profile)
        for field_name in (
            "name",
            "background",
            "objectives",
            "expected_outcomes",
            "start_date",
            "end_date",
            "description",
        ):
            if not getattr(merged, field_name).strip() and getattr(candidate, field_name).strip():
                setattr(merged, field_name, getattr(candidate, field_name))
        merged.confidence = max(merged.confidence, candidate.confidence)
        merged.evidence = _dedupe_evidence([*merged.evidence, *candidate.evidence], limit=20)
        merged.warnings = _dedupe_warnings([*merged.warnings, *candidate.warnings], limit=20)
    return merged


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
    # `description` predates the explicit semantic fields and is still sent by
    # historical clients. Keep it as a displayed-goal alias in both directions
    # so old and new AI responses remain readable during the migration.
    if not task_data["goal"].strip() and task_data["description"].strip():
        task_data["goal"] = task_data["description"].strip()
    if not task_data["description"].strip() and task_data["goal"].strip():
        task_data["description"] = task_data["goal"].strip()
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
    people = _person_candidates(existing_people)
    indexed_tasks, indexed_subtasks = _existing_task_index(existing_tasks or [])
    source_values = _source_index(chunks or [])
    project_profile = _reconcile_project_profile(envelope.project_profile, source_values)
    if not envelope.tasks and not project_profile.has_content():
        raise ProjectInitAiEmptyResult("AI 未提取到可用项目基本信息或任务")
    tasks = [
        _reconcile_task(task, people, indexed_tasks, indexed_subtasks, source_values)
        for task in envelope.tasks
    ]
    return ProjectInitAiResult(
        project_profile=project_profile,
        tasks=tasks,
        provider=provider,
        model_name=model_name,
    )
