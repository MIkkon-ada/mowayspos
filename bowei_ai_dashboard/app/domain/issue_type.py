"""Unified issue_type normalization helpers.

The backend uses canonical English keys for comparisons:
issue / risk / coordination / decision / unknown

For compatibility with existing UI/API expectations, callers can still keep
their storage/display values in Chinese and only use these helpers for
normalization and branching.
"""

from __future__ import annotations

TYPE_ISSUE = "issue"
TYPE_RISK = "risk"
TYPE_COORDINATION = "coordination"
TYPE_DECISION = "decision"
TYPE_UNKNOWN = "unknown"

_LABELS: dict[str, str] = {
    TYPE_ISSUE: "问题",
    TYPE_RISK: "风险",
    TYPE_COORDINATION: "协调事项",
    TYPE_DECISION: "决策事项",
    TYPE_UNKNOWN: "未知类型",
}

_ALIASES: dict[str, str] = {
    "问题": TYPE_ISSUE,
    "普通问题": TYPE_ISSUE,
    "issue": TYPE_ISSUE,
    "problem": TYPE_ISSUE,
    "风险": TYPE_RISK,
    "risk": TYPE_RISK,
    "协调": TYPE_COORDINATION,
    "协调事项": TYPE_COORDINATION,
    "协调中": TYPE_COORDINATION,
    "coordination": TYPE_COORDINATION,
    "待协调": TYPE_COORDINATION,
    "决策": TYPE_DECISION,
    "决策事项": TYPE_DECISION,
    "需决策": TYPE_DECISION,
    "needs_decision": TYPE_DECISION,
    "pending_decision": TYPE_DECISION,
    "decision": TYPE_DECISION,
    "需CEO决策": TYPE_DECISION,
    "待CEO决策": TYPE_DECISION,
    "待决策": TYPE_DECISION,
    "unknown": TYPE_UNKNOWN,
    "未知": TYPE_UNKNOWN,
}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def normalize(value: str | None) -> str:
    v = _clean(value)
    if not v:
        return TYPE_UNKNOWN
    return _ALIASES.get(v, _ALIASES.get(v.lower(), TYPE_UNKNOWN))


def is_issue(value: str | None) -> bool:
    return normalize(value) == TYPE_ISSUE


def is_risk(value: str | None) -> bool:
    return normalize(value) == TYPE_RISK


def is_coordination(value: str | None) -> bool:
    return normalize(value) == TYPE_COORDINATION


def is_decision(value: str | None) -> bool:
    return normalize(value) == TYPE_DECISION


def label(value: str | None) -> str:
    return _LABELS.get(normalize(value), _LABELS[TYPE_UNKNOWN])


def aliases_for(key: str) -> set[str]:
    normalized = normalize(key)
    aliases = {normalized, label(normalized)}
    for alias, target in _ALIASES.items():
        if target == normalized:
            aliases.add(alias)
    if normalized == TYPE_UNKNOWN:
        aliases.update({"", "未知", "unknown"})
    return aliases
