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

ALLOWED_CANDIDATE_TYPES = {
    "action_item",
    "decision",
    "decision_request",
    "risk",
    "progress",
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

_OWNER_MARKERS = (
    "负责",
    "跟进",
    "主导",
    "对接",
    "牵头",
    "安排",
    "处理",
    "负责人",
    "owner",
    "assignee",
)

_COMPLETED_PROGRESS_MARKERS = (
    "已完成",
    "已经完成",
    "完成了",
    "完成",
    "已上线",
    "已部署",
    "已收尾",
    "收尾完成",
    "落地完成",
)

_QUESTION_MARKERS = (
    "?",
    "？",
    "是否",
    "要不要",
    "需不需要",
    "能否",
    "可否",
    "是不是",
    "待定",
    "待确认",
    "请决策",
)


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


def validate_action_owner(candidate: Any, member_snapshot: Any) -> list[str]:
    if not isinstance(candidate, dict):
        return ["owner is not supported by transcript evidence"]

    owner_id, owner_name = _candidate_owner_identity(candidate)
    snapshot_names, snapshot_ids = _member_snapshot_index(member_snapshot)

    owner_known = False
    if owner_id is not None and str(owner_id) in snapshot_ids:
        owner_known = True
    if owner_name and owner_name in snapshot_names:
        owner_known = True

    if not owner_known:
        return ["owner is not part of project members"]

    evidence_texts = _candidate_evidence_texts(candidate)
    if owner_name and _has_explicit_owner_evidence(owner_name, evidence_texts):
        return []

    return ["owner is not supported by transcript evidence"]


def validate_candidate(candidate: Any, member_snapshot: Any = None) -> dict[str, Any]:
    row = dict(candidate) if isinstance(candidate, dict) else {}
    candidate_type = _candidate_type(row)

    if candidate_type:
        row["candidate_type"] = candidate_type

    messages = row.get("validation_messages")
    if isinstance(messages, list):
        validation_messages = list(messages)
    elif messages:
        validation_messages = [str(messages)]
    else:
        validation_messages = []
    row["validation_messages"] = validation_messages

    if candidate_type not in ALLOWED_CANDIDATE_TYPES:
        row["validation_status"] = "blocked"
        row["validation_messages"].append("unknown candidate type")
        return row

    status = "passed"

    if candidate_type == "action_item":
        owner_errors = validate_action_owner(row, member_snapshot)
        if owner_errors:
            row["validation_messages"].extend(owner_errors)
            owner_known = _owner_is_known(row, member_snapshot)
            status = "needs_confirmation" if owner_known else "blocked"

    acceptance_criteria = str(row.get("acceptance_criteria") or "").strip()
    if acceptance_criteria and not _field_has_evidence(acceptance_criteria, row):
        row["acceptance_criteria"] = ""
        row["validation_messages"].append("acceptance_criteria requires transcript evidence")
        status = "blocked"
    else:
        row["acceptance_criteria"] = acceptance_criteria

    content = _candidate_content(row)
    if candidate_type in {"risk", "decision"} and _looks_like_completed_progress(content):
        row["validation_messages"].append("completed progress cannot be classified as risk or decision")
        status = "blocked"

    if candidate_type == "decision" and _looks_like_unmade_question(content):
        row["validation_messages"].append("unmade question cannot be classified as decision")
        status = "blocked"

    row["validation_status"] = status
    return row


def validate_candidates(candidates: Any, member_snapshot: Any = None) -> list[dict[str, Any]]:
    if candidates is None:
        return []
    if isinstance(candidates, dict):
        items = [candidates]
    else:
        items = list(candidates)
    return [validate_candidate(candidate, member_snapshot) for candidate in items]


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

    if len(expression) >= 3 and expression[:2] in {"本周", "下周"}:
        scope = expression[:2]
        weekday_text = expression[2:]
        if weekday_text in _WEEKDAY_MAP:
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


def _candidate_type(candidate: dict[str, Any]) -> str:
    raw = candidate.get("candidate_type", candidate.get("type", ""))
    return str(raw).strip().lower()


def _candidate_owner_identity(candidate: dict[str, Any]) -> tuple[Any, str]:
    owner_id = candidate.get("owner_person_id", candidate.get("member_person_id", candidate.get("owner_id")))
    owner_name = ""
    for key in ("owner_name", "member", "owner", "person_name", "name"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            owner_name = value.strip()
            break
    return owner_id, owner_name


def _owner_is_known(candidate: dict[str, Any], member_snapshot: Any) -> bool:
    owner_id, owner_name = _candidate_owner_identity(candidate)
    snapshot_names, snapshot_ids = _member_snapshot_index(member_snapshot)

    if owner_id is not None and str(owner_id) in snapshot_ids:
        return True
    if owner_name and owner_name in snapshot_names:
        return True
    return False


def _candidate_content(candidate: dict[str, Any]) -> str:
    for key in ("content", "text", "summary", "action", "title"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _candidate_evidence_texts(candidate: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    evidence = candidate.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                for key in ("quote", "evidence_quote", "content", "text"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        texts.append(value.strip())
                        break
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())

    for key in ("evidence_quote", "content", "text", "summary", "action"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
            break

    return texts


def _member_snapshot_index(member_snapshot: Any) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    ids: set[str] = set()

    if isinstance(member_snapshot, dict):
        members = member_snapshot.get("members")
        if isinstance(members, list):
            for item in members:
                if isinstance(item, dict):
                    person_id = item.get("person_id", item.get("id"))
                    if person_id is not None:
                        ids.add(str(person_id))
                    name = item.get("name", item.get("person_name_snapshot"))
                    if isinstance(name, str) and name.strip():
                        names.add(name.strip())
        for key, value in member_snapshot.items():
            if key == "members" or value is None:
                continue
            ids.add(str(key))
            if isinstance(value, str) and value.strip():
                names.add(value.strip())
            elif isinstance(value, dict):
                name = value.get("name", value.get("person_name_snapshot"))
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())
    elif isinstance(member_snapshot, list):
        for item in member_snapshot:
            if isinstance(item, str) and item.strip():
                names.add(item.strip())
            elif isinstance(item, dict):
                person_id = item.get("person_id", item.get("id"))
                if person_id is not None:
                    ids.add(str(person_id))
                name = item.get("name", item.get("person_name_snapshot"))
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())

    return names, ids


def _has_explicit_owner_evidence(owner_name: str, texts: list[str]) -> bool:
    if not owner_name:
        return False

    name = re.escape(owner_name)
    for text in texts:
        if owner_name not in text:
            continue
        if re.search(rf"{name}.{{0,12}}(?:负责|跟进|主导|对接|牵头|安排|处理|负责人)", text):
            return True
        if re.search(rf"(?:负责|跟进|主导|对接|牵头|安排|处理).{{0,12}}{name}", text):
            return True
        if re.search(rf"由{name}.{{0,12}}(?:负责|跟进|主导|对接|牵头|安排|处理)", text):
            return True
        if re.search(rf"{name}.{{0,8}}(?:是)?(?:负责人|owner|assignee)", text, flags=re.IGNORECASE):
            return True
    return False


def _field_has_evidence(value: str, candidate: dict[str, Any]) -> bool:
    if not value:
        return False
    needle = value.casefold()
    for text in _candidate_evidence_texts(candidate):
        if needle in text.casefold():
            return True
    return False


def _looks_like_completed_progress(text: str) -> bool:
    normalized = text.casefold()
    return any(marker.casefold() in normalized for marker in _COMPLETED_PROGRESS_MARKERS)


def _looks_like_unmade_question(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if "?" in normalized or "？" in normalized:
        return True
    return any(marker in normalized for marker in _QUESTION_MARKERS)
