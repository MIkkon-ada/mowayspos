"""Safe normalization and classification for project-init model responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .project_init_ai_contracts import _RawEnvelope, _safe_validation_errors


_PROFILE_TEXT_FIELDS = (
    "name",
    "background",
    "objectives",
    "expected_outcomes",
    "start_date",
    "end_date",
    "description",
)
_TASK_TEXT_FIELDS = (
    "description",
    "goal",
    "acceptance_criteria",
    "process",
    "owner_name",
    "priority",
    "status",
    "plan_start",
    "plan_end",
)
_SUBTASK_TEXT_FIELDS = (
    "description",
    "assignee_name",
    "priority",
    "status",
    "plan_start",
    "plan_end",
    "evaluation_standard",
)
_TASK_SERVER_FIELDS = {
    "owner_id",
    "confidence",
    "merge_status",
    "duplicate_of",
    "duplicate_reason",
    "warnings",
    "source",
}
_SUBTASK_SERVER_FIELDS = {
    "assignee_id",
    "helper_ids",
    "confidence",
    "merge_status",
    "duplicate_of",
    "duplicate_reason",
    "warnings",
    "source",
}
_PROFILE_SERVER_FIELDS = {"confidence", "warnings"}


@dataclass(frozen=True)
class DraftResponseDiagnostic:
    code: str
    paths: tuple[dict[str, str], ...] = ()
    normalized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "paths": [dict(item) for item in self.paths],
            "normalized": self.normalized,
        }


class _JsonResponseError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _parse_one_json(raw: str) -> Any:
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
                    raise _JsonResponseError("json_malformed")
                stack.pop()
                if not stack:
                    try:
                        values.append(json.loads(text[start : index + 1]))
                    except ValueError as exc:
                        raise _JsonResponseError("json_malformed") from exc
                    cursor = index + 1
                    break
        else:
            raise _JsonResponseError("json_malformed")
    if len(values) != 1:
        raise _JsonResponseError("json_missing_or_multiple")
    return values[0]


def _text_defaults(value: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if value.get(field) is None:
            value[field] = ""


def _normalize_evidence(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    result.pop("source_label", None)
    return result


def _normalize_subtask(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for field in _SUBTASK_SERVER_FIELDS:
        result.pop(field, None)
    if isinstance(result.get("evidence"), list):
        result["evidence"] = [_normalize_evidence(item) for item in result["evidence"]]
    _text_defaults(result, _SUBTASK_TEXT_FIELDS)
    result.setdefault("helper_names", [])
    return result


def _normalize_task(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for field in _TASK_SERVER_FIELDS:
        result.pop(field, None)
    if "deadline" in result and "plan_end" not in result:
        result["plan_end"] = result.pop("deadline")
    if "startDate" in result and "plan_start" not in result:
        result["plan_start"] = result.pop("startDate")
    if "endDate" in result and "plan_end" not in result:
        result["plan_end"] = result.pop("endDate")
    if isinstance(result.get("evidence"), list):
        result["evidence"] = [_normalize_evidence(item) for item in result["evidence"]]
    if isinstance(result.get("subtasks"), list):
        result["subtasks"] = [_normalize_subtask(item) for item in result["subtasks"]]
    _text_defaults(result, _TASK_TEXT_FIELDS)
    return result


def _normalize_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    profile = result.get("project_profile")
    if isinstance(profile, dict):
        profile = dict(profile)
        for field in _PROFILE_SERVER_FIELDS:
            profile.pop(field, None)
        if "startDate" in profile and "start_date" not in profile:
            profile["start_date"] = profile.pop("startDate")
        if "endDate" in profile and "end_date" not in profile:
            profile["end_date"] = profile.pop("endDate")
        if isinstance(profile.get("evidence"), list):
            profile["evidence"] = [_normalize_evidence(item) for item in profile["evidence"]]
        _text_defaults(profile, _PROFILE_TEXT_FIELDS)
        result["project_profile"] = profile
    if isinstance(result.get("tasks"), list):
        result["tasks"] = [_normalize_task(item) for item in result["tasks"]]
    return result


def normalize_project_init_response(raw: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload = _normalize_payload(_parse_one_json(raw))
    if not isinstance(payload, dict):
        raise _JsonResponseError("schema_invalid")
    return payload, []


def classify_project_init_response(raw: str) -> DraftResponseDiagnostic:
    try:
        payload, _ = normalize_project_init_response(raw)
        _RawEnvelope.model_validate(payload)
    except _JsonResponseError as exc:
        return DraftResponseDiagnostic(code=exc.code)
    except ValidationError as exc:
        return DraftResponseDiagnostic(
            code="schema_invalid",
            paths=tuple(_safe_validation_errors(exc)),
        )
    return DraftResponseDiagnostic(code="", normalized=True)


def build_project_init_repair_prompt(original_prompt: str, diagnostics: list[dict[str, str]]) -> str:
    return (
        "修复上一轮项目立项草稿的结构，只返回一个严格 JSON 对象。"
        "不得新增、删除或改写任务事实、人员、日期和 evidence 来源；"
        "可选字符串缺失时使用空字符串，保持 project_profile 和 tasks 结构。"
        f"\n需要修复的字段路径：{json.dumps(diagnostics, ensure_ascii=False)}"
        f"\n原始提取要求和来源：{original_prompt}"
    )
