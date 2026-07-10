"""Shared task/subtask status semantics for the work-progress table."""

from __future__ import annotations


S_NOT_STARTED = "未开始"
S_IN_PROGRESS = "进行中"
S_COMPLETED = "已完成"
S_DELAYED = "延期"
S_PAUSED = "暂缓"
S_ARCHIVED = "已归档"

ALIASES = {
    "not_started": S_NOT_STARTED,
    "notstarted": S_NOT_STARTED,
    "未启动": S_NOT_STARTED,
    "推进中": S_IN_PROGRESS,
    "in_progress": S_IN_PROGRESS,
    "completed": S_COMPLETED,
    "完成": S_COMPLETED,
    "delayed": S_DELAYED,
    "已延期": S_DELAYED,
    "paused": S_PAUSED,
    "暂停": S_PAUSED,
    "已暂停": S_PAUSED,
    "archived": S_ARCHIVED,
}

TERMINAL = {S_COMPLETED, S_ARCHIVED}
ACTIVE = {S_IN_PROGRESS, S_DELAYED}
HOLDING = {S_PAUSED}
NOT_STARTED = {S_NOT_STARTED}


def normalize(status: str | None) -> str:
    raw = (status or "").strip()
    if not raw:
        return S_NOT_STARTED
    return ALIASES.get(raw, raw)


def is_completed(status: str | None) -> bool:
    return normalize(status) == S_COMPLETED


def derive_parent_status(current_status: str | None, subtask_statuses: list[str]) -> str:
    """Derive key-task status from child subtasks."""
    current = normalize(current_status)
    statuses = [normalize(status) for status in subtask_statuses]
    if not statuses:
        return current
    if current == S_ARCHIVED:
        return current
    if all(status == S_COMPLETED for status in statuses):
        return S_COMPLETED if current == S_COMPLETED else S_IN_PROGRESS
    if any(status == S_DELAYED for status in statuses):
        return S_DELAYED
    if any(status in {S_IN_PROGRESS, S_COMPLETED} for status in statuses):
        return S_IN_PROGRESS
    if any(status == S_PAUSED for status in statuses):
        return S_PAUSED
    return S_NOT_STARTED
