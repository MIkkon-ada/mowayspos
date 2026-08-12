from __future__ import annotations

import json
import re
from collections.abc import Iterable


_YEAR_DATE = re.compile(r"(?<!\d)(?:19|20)\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?")
_RELATIVE_MONTH_DAY = re.compile(r"(?<!\d)(\d{1,2}月\d{1,2}日?前)")


def _source_has_explicit_year(text: str) -> bool:
    return bool(_YEAR_DATE.search(text or ""))


def normalize_action_items(items: Iterable[object], source_text: str) -> list[dict]:
    """Keep deadlines source-grounded and reject model-invented calendar years."""
    source = source_text or ""
    source_has_year = _source_has_explicit_year(source)
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        task = str(row.get("task") or "")
        deadline = str(row.get("deadline") or "").strip()
        evidence = f"{task}\n{source}"
        relative_match = _RELATIVE_MONTH_DAY.search(evidence)
        if deadline and re.search(r"(?:19|20)\d{2}[-/]", deadline) and not source_has_year:
            row["deadline"] = relative_match.group(1) if relative_match else "待确认"
        elif not deadline:
            row["deadline"] = "待确认"
        else:
            row["deadline"] = deadline
        row["acceptance_criteria"] = str(row.get("acceptance_criteria") or "待确认").strip()
        row["evidence_quote"] = str(
            row.get("evidence_quote") or row.get("evidence") or "待确认"
        ).strip()
        normalized.append(row)
    return normalized


def normalize_action_items_json(value: str, source_text: str) -> str:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return value or "[]"
    return json.dumps(normalize_action_items(parsed, source_text), ensure_ascii=False)
