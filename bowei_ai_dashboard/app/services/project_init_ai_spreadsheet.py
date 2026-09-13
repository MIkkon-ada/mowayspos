"""Deterministic spreadsheet drafting and worksheet evidence recovery."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .project_init_ai_contracts import (
    AgentTask,
    Evidence,
    PersonCandidate,
    ProjectInitAiError,
    ProjectInitAiResult,
)
from .project_init_ai_normalization import (
    _dedupe_strings,
    _existing_task_index,
    _is_calendar_date,
    _match_person,
    _normalise_title,
    _person_candidates,
    _source_parts,
    normalize_agent_result,
)
from .project_init_file_parser import SourceChunk


_MAX_EXCEL_COLUMN = 16_384  # XFD
_MAX_EXCEL_ROW = 1_048_576
_YEAR_MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")
_ISO_DATE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])")
_WORKSHEET_RANGE = re.compile(
    r"^(?P<sheet>'(?:[^']|'')+'|[^!]+)!(?P<start_column>[A-Z]+)(?P<start_row>\d+):"
    r"(?P<end_column>[A-Z]+)(?P<end_row>\d+)$",
    re.IGNORECASE,
)
_WORK_PLAN_HEADER_ALIASES = {
    "专项": {"专项", "主要工作", "重点工作", "重点工作名称", "工作模块", "一级任务"},
    "关键任务": {"关键任务", "任务名称", "任务", "子任务", "工作事项", "二级任务"},
    "关键成果": {"关键成果", "目标成果", "成果", "交付物", "预期成果"},
    "目标": {"目标", "预期目标", "工作目标", "目标描述"},
    "验收标准": {"验收标准", "验收标准与关键成果", "评价标准", "验证标准", "交付标准"},
    "完成标准": {"完成标准"},
    "推进流程": {"推进流程", "实施流程", "流程", "执行流程", "工作流程"},
    "统筹人": {"统筹人", "统筹负责人", "项目统筹", "项目负责人"},
    "负责人": {"负责人", "责任人", "执行人", "执行负责人", "任务负责人"},
    "协同成员": {"协同成员", "协助人", "协同人", "协作者", "协作人"},
    "计划时间": {"计划时间", "开始时间", "开始日期", "计划日期"},
    "计划开始": {"计划开始时间", "计划开始日期"},
    "计划结束": {"计划结束时间", "计划结束日期", "计划计划结束时间"},
    "当前状态": {"当前状态", "状态", "进度", "任务状态", "完成情况"},
    "问题与协调": {"问题与协调", "备注", "说明", "问题", "协调事项"},
}
_WORK_PLAN_HEADER_KEYS = {
    canonical: {
        normalised
        for alias in aliases
        for normalised in [re.sub(r"[\s：:（）()\[\]【】_-]+", "", alias).casefold()]
    }
    for canonical, aliases in _WORK_PLAN_HEADER_ALIASES.items()
}
_CHINESE_MONTH_RANGE = re.compile(
    r"(?:(?P<start_year>20\d{2})[-年])?(?P<start_month>\d{1,2})"
    r"(?:\s*(?:-|~|至)\s*(?:(?P<end_year>20\d{2})[-年])?(?P<end_month>\d{1,2}))?月?"
)

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


def _column_number(value: str) -> int:
    result = 0
    for character in value.upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _worksheet_range(value: str) -> tuple[str, int, int, int, int] | None:
    match = _WORKSHEET_RANGE.fullmatch(value.strip())
    if not match:
        return None
    start_column = _column_number(match.group("start_column"))
    end_column = _column_number(match.group("end_column"))
    start_row = int(match.group("start_row"))
    end_row = int(match.group("end_row"))
    if (
        not 1 <= start_column <= _MAX_EXCEL_COLUMN
        or not 1 <= end_column <= _MAX_EXCEL_COLUMN
        or not 1 <= start_row <= _MAX_EXCEL_ROW
        or not 1 <= end_row <= _MAX_EXCEL_ROW
        or start_column > end_column
        or start_row > end_row
    ):
        return None
    return match.group("sheet").casefold(), start_column, start_row, end_column, end_row


def _enclosed_worksheet_sources(
    raw: Evidence,
    sources: list[tuple[str, str, str, int | None]],
) -> list[tuple[str, str, str, int | None]]:
    raw_range = _worksheet_range(raw.location)
    if raw_range is None:
        return []
    sheet, start_column, start_row, end_column, end_row = raw_range
    matches: list[tuple[str, str, str, int | None]] = []
    for source in sources:
        file_name, location, _text, attachment_id = source
        if file_name != raw.file_name or attachment_id != raw.attachment_id:
            continue
        source_range = _worksheet_range(location)
        if source_range is None:
            continue
        source_sheet, source_start_column, source_start_row, source_end_column, source_end_row = source_range
        if (
            source_sheet == sheet
            and start_column <= source_start_column <= source_end_column <= end_column
            and start_row <= source_start_row <= source_end_row <= end_row
        ):
            matches.append(source)
    return matches


def _repair_coarse_worksheet_evidence(
    evidence: list[Evidence],
    sources: list[tuple[str, str, str, int | None]],
    titles: Iterable[str],
) -> list[Evidence]:
    """Replace a model's broad worksheet range with a title-matched source row.

    This recovery is deliberately narrow: it never accepts a different file or
    attachment, and it requires the declared range to enclose a real source row
    containing the task title. All other untraceable citations still fail closed.
    """
    title_values = [
        _normalise_title(title)
        for title in titles
        if _normalise_title(title)
    ]
    repaired: list[Evidence] = []
    for item in evidence:
        if _evidence_traceability_error(item, sources) != "untraceable_location":
            repaired.append(item)
            continue
        candidates = _enclosed_worksheet_sources(item, sources)
        source = next(
            (
                candidate
                for candidate in candidates
                if any(title in _normalise_title(candidate[2]) for title in title_values)
            ),
            None,
        )
        if source is None:
            repaired.append(item)
            continue
        repaired.append(
            Evidence(
                attachment_id=source[3],
                file_name=source[0],
                location=source[1],
                excerpt=item.excerpt,
            )
        )
    return repaired


def _repair_batch_evidence(task: AgentTask, batch: list[tuple[str, str, str, int | None]]) -> AgentTask:
    repaired_task = task.model_copy(deep=True)
    repaired_task.evidence = _repair_coarse_worksheet_evidence(
        repaired_task.evidence,
        batch,
        [repaired_task.title],
    )
    for subtask in repaired_task.subtasks:
        subtask.evidence = _repair_coarse_worksheet_evidence(
            subtask.evidence,
            batch,
            [subtask.title, repaired_task.title],
        )
    return repaired_task


def _spreadsheet_plan_dates(value: str) -> tuple[str, str]:
    """Derive only explicitly supported spreadsheet month values into plan dates."""
    clean_value = re.sub(r"\s+", "", str(value or ""))
    if _ISO_DATE.fullmatch(clean_value) and _is_calendar_date(clean_value):
        return clean_value, ""
    if _YEAR_MONTH.fullmatch(clean_value):
        return f"{clean_value}-01", ""
    match = _CHINESE_MONTH_RANGE.fullmatch(clean_value)
    if match is None:
        return "", ""
    start_year = match.group("start_year")
    end_year = match.group("end_year") or start_year
    start_month = int(match.group("start_month"))
    end_month_text = match.group("end_month")
    if not start_year or not 1 <= start_month <= 12:
        return "", ""
    plan_start = f"{start_year}-{start_month:02d}-01"
    if end_month_text is None:
        return plan_start, ""
    end_month = int(end_month_text)
    if not end_year or not 1 <= end_month <= 12:
        return plan_start, ""
    if (int(end_year), end_month) < (int(start_year), start_month):
        return plan_start, ""
    return plan_start, f"{end_year}-{end_month:02d}"


def _explicit_spreadsheet_date(value: str) -> str:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}:\d{2})?", str(value or "").strip())
    if match and _is_calendar_date(match.group(1)):
        return match.group(1)
    return ""


def _bounded_spreadsheet_text(value: str, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _split_numbered_spreadsheet_items(value: str) -> list[str]:
    """Split a cell containing numbered items while preserving unnumbered text."""
    text = str(value or "").strip()
    if not text:
        return []
    markers = list(re.finditer(r"(?<!\d)\d{1,3}\s*[.．、)]\s*", text))
    if not markers:
        return [text]
    items: list[str] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        item = text[marker.end():end].strip()
        if item:
            items.append(item)
    return items or [text]


def _split_helper_names(value: str) -> list[str]:
    return [
        _bounded_spreadsheet_text(item, 50)
        for item in re.split(r"[、，,；;/]+", str(value or ""))
        if item.strip()
    ]


def _normalise_spreadsheet_header(value: str) -> str:
    return re.sub(r"[\s：:（）()\[\]【】_-]+", "", str(value or "")).casefold()


def _normalise_work_plan_row(
    headers: list[str], values: list[str], *, require_full_coverage: bool = False,
) -> dict[str, str] | None:
    """Map common, non-standard spreadsheet headers to the review draft fields."""

    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalised_header = _normalise_spreadsheet_header(header)
        for canonical, alias_keys in _WORK_PLAN_HEADER_KEYS.items():
            if normalised_header in alias_keys:
                columns.setdefault(canonical, index)
                break
    if not {"专项", "关键任务"}.issubset(columns):
        return None
    if require_full_coverage:
        projected_columns = set(columns.values())
        if any(value.strip() and index not in projected_columns for index, value in enumerate(values)):
            return None
    return {
        canonical: values[index].strip() if index < len(values) else ""
        for canonical, index in columns.items()
    }


def _structured_spreadsheet_rows(
    sources: list[tuple[str, str, str, int | None]],
    people: list[PersonCandidate],
    *,
    require_full_coverage: bool = False,
) -> list[dict[str, Any]]:
    """Build a traceable review draft when a work-progress spreadsheet is explicit."""
    task_index: dict[str, dict[str, Any]] = {}
    worksheet_contexts: dict[tuple[str, str], dict[str, str]] = {}
    for file_name, location, text, attachment_id in sources:
        worksheet_range = _worksheet_range(location)
        if not file_name.casefold().endswith((".xlsx", ".xls")) or worksheet_range is None:
            continue
        lines = str(text or "").splitlines()
        if len(lines) < 2 or "\t" not in lines[0]:
            if require_full_coverage and text.strip():
                return []
            continue
        headers = [item.strip() for item in lines[0].split("\t")]
        if require_full_coverage and _normalise_work_plan_row(headers, []) is None:
            return []
        worksheet_key = (file_name, worksheet_range[0])
        context = worksheet_contexts.setdefault(worksheet_key, {})
        for values_line in lines[1:]:
            if not values_line.strip():
                continue
            if "\t" not in values_line:
                if require_full_coverage:
                    return []
                continue
            values = [item.strip() for item in values_line.split("\t")]
            row = _normalise_work_plan_row(headers, values, require_full_coverage=require_full_coverage)
            if row is None:
                if require_full_coverage:
                    return []
                continue
            raw_task_title = _bounded_spreadsheet_text(row.get("专项", ""), 200)
            if raw_task_title:
                # A non-empty workstream cell starts a new parent context. Do
                # not leak the previous workstream's result or coordinator.
                context = {"专项": raw_task_title}
                worksheet_contexts[worksheet_key] = context
            task_title = raw_task_title or context.get("专项", "")
            subtask_titles = _split_numbered_spreadsheet_items(row.get("关键任务", ""))
            if not task_title or not subtask_titles:
                if require_full_coverage:
                    return []
                continue
            subtask_title = subtask_titles[0]

            for field in (
                "关键成果",
                "目标",
                "验收标准",
                "完成标准",
                "推进流程",
                "统筹人",
                "计划时间",
                "计划开始",
                "计划结束",
                "当前状态",
            ):
                max_length = {
                    "关键成果": 2_000,
                    "目标": 2_000,
                    "验收标准": 2_000,
                    "完成标准": 2_000,
                    "推进流程": 2_000,
                    "统筹人": 50,
                    "计划时间": 50,
                    "计划开始": 50,
                    "计划结束": 50,
                    "当前状态": 50,
                }[field]
                value = _bounded_spreadsheet_text(row.get(field, ""), max_length)
                if value:
                    context[field] = value
            coordinator = context.get("统筹人", "")
            fallback_start, fallback_end = _spreadsheet_plan_dates(
                row.get("计划时间", "").strip() or context.get("计划时间", "")
            )
            plan_start = _explicit_spreadsheet_date(
                row.get("计划开始", "").strip() or context.get("计划开始", "")
            ) or fallback_start
            plan_end = _explicit_spreadsheet_date(
                row.get("计划结束", "").strip() or context.get("计划结束", "")
            ) or fallback_end
            responsible_names = _split_helper_names(row.get("负责人", ""))
            matched_responsible_names = [
                name for name in responsible_names if _match_person(name, people)[0] is not None
            ]
            assignee_name = (
                matched_responsible_names[0]
                if matched_responsible_names
                else (responsible_names[0] if responsible_names else coordinator)
            )
            helper_names = _dedupe_strings([
                *(name for name in responsible_names if name != assignee_name),
                *_split_helper_names(row.get("协同成员", "")),
            ])[:20]
            evidence = [{
                "attachment_id": attachment_id,
                "file_name": file_name,
                "location": location,
            }]
            task_key = _normalise_title(task_title)
            task = task_index.get(task_key)
            if task is None:
                task = {
                    "title": task_title,
                    "description": context.get("关键成果", "").strip()
                    or context.get("目标", "").strip()
                    or context.get("验收标准", "").strip()
                    or row.get("完成标准", "").strip(),
                    "goal": context.get("目标", "").strip(),
                    "acceptance_criteria": (
                        context.get("验收标准", "").strip()
                        or context.get("关键成果", "").strip()
                        or context.get("完成标准", "").strip()
                    ),
                    "process": context.get("推进流程", "").strip(),
                    "owner_name": coordinator,
                    "status": context.get("当前状态", "").strip(),
                    "plan_start": plan_start,
                    "plan_end": plan_end,
                    "evidence": evidence,
                    "subtasks": [],
                }
                task_index[task_key] = task
            else:
                if not task["description"] and context.get("关键成果", "").strip():
                    task["description"] = context["关键成果"].strip()
                if not task["description"] and context.get("目标", "").strip():
                    task["description"] = context["目标"].strip()
                if not task["description"] and context.get("验收标准", "").strip():
                    task["description"] = context["验收标准"].strip()
                elif not task["description"] and row.get("完成标准", "").strip():
                    task["description"] = row["完成标准"].strip()
                if not task["goal"] and context.get("目标", "").strip():
                    task["goal"] = context["目标"].strip()
                if not task["acceptance_criteria"]:
                    task["acceptance_criteria"] = (
                        context.get("验收标准", "").strip()
                        or context.get("关键成果", "").strip()
                        or context.get("完成标准", "").strip()
                    )
                if not task["process"] and context.get("推进流程", "").strip():
                    task["process"] = context["推进流程"].strip()
                if not task["owner_name"] and coordinator:
                    task["owner_name"] = coordinator
                if not task["status"] and context.get("当前状态", "").strip():
                    task["status"] = context["当前状态"].strip()
                if not task["plan_start"] and plan_start:
                    task["plan_start"] = plan_start
                if not task["plan_end"] and plan_end:
                    task["plan_end"] = plan_end
                if len(task["evidence"]) < 10:
                    task["evidence"].append(evidence[0])
            subtask_data = {
                "description": _bounded_spreadsheet_text(row.get("问题与协调", ""), 2_000),
                "assignee_name": assignee_name,
                "helper_names": helper_names,
                "status": _bounded_spreadsheet_text(row.get("当前状态", ""), 50),
                "plan_start": plan_start,
                "plan_end": plan_end,
                "evaluation_standard": _bounded_spreadsheet_text(
                    row.get("完成标准", "") or row.get("验收标准", ""),
                    1_000,
                ),
                "evidence": evidence,
            }
            task["subtasks"].extend(
                [
                    {"title": _bounded_spreadsheet_text(title, 200), **subtask_data}
                    for title in subtask_titles
                ]
            )
    return list(task_index.values())


def _structured_spreadsheet_fallback(
    sources: list[tuple[str, str, str, int | None]],
    people: list[PersonCandidate],
    existing_tasks: list[dict[str, Any]],
    provider: str,
    *,
    model_name: str = "structured-spreadsheet-fallback",
    require_full_coverage: bool = False,
) -> ProjectInitAiResult | None:
    # A deterministic workbook projection must never make other uploaded
    # sources disappear. Mixed uploads stay on the evidence-bound AI route so
    # the model can consider every source, or fail closed if that route is not
    # available.
    if not sources or not all(
        file_name.casefold().endswith((".xlsx", ".xls"))
        and _worksheet_range(location) is not None
        for file_name, location, _text, _attachment_id in sources
    ):
        return None
    tasks = _structured_spreadsheet_rows(sources, people, require_full_coverage=require_full_coverage)
    if not tasks:
        return None
    return normalize_agent_result(
        {"tasks": tasks},
        people,
        existing_tasks=existing_tasks,
        chunks=sources,
        provider=provider,
        model_name=model_name,
    )


def generate_structured_project_init_draft(
    chunks: Iterable[SourceChunk | dict[str, Any]],
    existing_people: Iterable[PersonCandidate | dict[str, Any]],
    existing_tasks: Iterable[dict[str, Any]],
) -> ProjectInitAiResult | None:
    """Project explicit Excel rows into a draft, or defer to model analysis.

    The caller must first exclude sources requiring visual interpretation.
    Mixed sources, invalid worksheet ranges, and any unrecognized meaningful
    chunk or row return no draft so model analysis can consider the full input.
    """
    source_values = [_source_parts(chunk) for chunk in chunks]
    people = _person_candidates(existing_people)
    indexed_tasks, _ = _existing_task_index(existing_tasks)
    return _structured_spreadsheet_fallback(
        source_values, people, indexed_tasks, "local-rule",
        require_full_coverage=True,
    )
