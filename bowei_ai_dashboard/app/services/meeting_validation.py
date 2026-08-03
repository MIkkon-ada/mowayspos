from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

VALIDATION_STATES = {
    "passed",
    "warning",
    "needs_confirmation",
    "blocked",
}

_WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


def validate_evidence(ref: Any, transcript: Any, expected_hash: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    if not isinstance(ref, dict):
        return [{"code": "invalid_ref", "status": "blocked"}]

    start = ref.get("start")
    end = ref.get("end")
    quote = ref.get("quote")

    if (
        not isinstance(transcript, str)
        or not isinstance(expected_hash, str)
        or not isinstance(quote, str)
    ):
        return [{"code": "invalid_ref", "status": "blocked"}]

    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
        or end > len(transcript)
    ):
        return [{"code": "invalid_span", "status": "blocked"}]

    span = transcript[start:end]
    if span != quote:
        issues.append({"code": "quote_mismatch", "status": "blocked"})

    normalized_expected = expected_hash.removeprefix("sha256:").lower()
    actual_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    if actual_hash != normalized_expected:
        issues.append({"code": "hash_mismatch", "status": "blocked"})

    return issues


def resolve_temporal_expression(
    expression: str,
    reference_date: date | datetime | str,
    timezone: str = "Asia/Shanghai",
) -> dict[str, Any]:
    reference = _coerce_date(reference_date)
    expression = expression.strip()

    explicit = _resolve_explicit_expression(expression, reference)
    if explicit is not None:
        start, end, status = explicit
        return {
            "expression": expression,
            "start": start,
            "end": end,
            "status": status,
            "reference_date": reference.isoformat(),
            "timezone": timezone,
        }

    if _is_ambiguous_expression(expression):
        return {
            "expression": expression,
            "start": None,
            "end": None,
            "status": "needs_confirmation",
            "reference_date": reference.isoformat(),
            "timezone": timezone,
        }

    return {
        "expression": expression,
        "start": None,
        "end": None,
        "status": "needs_confirmation",
        "reference_date": reference.isoformat(),
        "timezone": timezone,
    }


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("reference_date must be a date, datetime, or ISO date string")


def _resolve_explicit_expression(expression: str, reference: date) -> tuple[str, str, str] | None:
    if expression == "明天":
        target = reference + timedelta(days=1)
        return target.isoformat(), target.isoformat(), "passed"
    if expression == "后天":
        target = reference + timedelta(days=2)
        return target.isoformat(), target.isoformat(), "passed"
    if expression == "下周":
        start = _start_of_next_week(reference)
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat(), "passed"

    match = re.fullmatch(r"(本周|下周)([一二三四五六日天])", expression)
    if match:
        scope, weekday_text = match.groups()
        target = _weekday_for_scope(reference, scope, weekday_text)
        iso = target.isoformat()
        return iso, iso, "passed"

    return None


def _start_of_next_week(reference: date) -> date:
    start_of_week = reference - timedelta(days=reference.weekday())
    return start_of_week + timedelta(days=7)


def _weekday_for_scope(reference: date, scope: str, weekday_text: str) -> date:
    weekday_index = _WEEKDAY_MAP[weekday_text]
    start_of_week = reference - timedelta(days=reference.weekday())
    if scope == "下周":
        start_of_week += timedelta(days=7)
    return start_of_week + timedelta(days=weekday_index)


def _is_ambiguous_expression(expression: str) -> bool:
    if expression in {"尽快", "近期", "过几天", "下一阶段", "有时间的时候", "月底左右"}:
        return True
    if re.search(r"\d{1,2}月\d{1,2}日", expression) and "年" not in expression:
        return True
    return False
