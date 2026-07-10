"""Shared source_type normalization helpers."""

from __future__ import annotations


MANUAL = "manual"
VOICE = "voice"
MEETING = "meeting"
AI_EXTRACT = "ai_extract"
IMPORT = "import"
UNKNOWN = "unknown"

_LABELS: dict[str, str] = {
    MANUAL: "人工录入",
    VOICE: "语音提交",
    MEETING: "会议纪要",
    AI_EXTRACT: "AI提取",
    IMPORT: "批量导入",
    UNKNOWN: "未知来源",
}

_ALIASES: dict[str, str] = {
    "人工录入": MANUAL,
    "人工补录": MANUAL,
    "人工补录确认": MANUAL,
    "manual": MANUAL,
    "text": MANUAL,
    "typed": MANUAL,
    "input": MANUAL,
    "文字更新": MANUAL,
    "语音": VOICE,
    "语音提交": VOICE,
    "语音更新": VOICE,
    "voice": VOICE,
    "speech": VOICE,
    "会议": MEETING,
    "会议纪要": MEETING,
    "会议记录": MEETING,
    "meeting": MEETING,
    "meeting_minutes": MEETING,
    "kickoff_meeting": MEETING,
    "AI提取": AI_EXTRACT,
    "AI 提取": AI_EXTRACT,
    "AI确认": AI_EXTRACT,
    "AI确认写入": AI_EXTRACT,
    "AI确认入库": AI_EXTRACT,
    "ai": AI_EXTRACT,
    "ai_extract": AI_EXTRACT,
    "extracted": AI_EXTRACT,
    "导入": IMPORT,
    "批量导入": IMPORT,
    "Excel导入": IMPORT,
    "Excel预定成果": IMPORT,
    "Excel预定成果 + AI确认": IMPORT,
    "大纲导入": IMPORT,
    "excel": IMPORT,
    "import": IMPORT,
    "batch_import": IMPORT,
}

_ALIASES_BY_KEY: dict[str, tuple[str, ...]] = {
    MANUAL: (
        MANUAL,
        "人工录入",
        "人工补录",
        "人工补录确认",
        "manual",
        "text",
        "typed",
        "input",
        "文字更新",
    ),
    VOICE: (
        VOICE,
        "语音",
        "语音提交",
        "语音更新",
        "voice",
        "speech",
    ),
    MEETING: (
        MEETING,
        "会议",
        "会议纪要",
        "会议记录",
        "meeting",
        "meeting_minutes",
        "kickoff_meeting",
    ),
    AI_EXTRACT: (
        AI_EXTRACT,
        "AI提取",
        "AI 提取",
        "AI确认",
        "AI确认写入",
        "AI确认入库",
        "ai",
        "ai_extract",
        "extracted",
    ),
    IMPORT: (
        IMPORT,
        "导入",
        "批量导入",
        "Excel导入",
        "Excel预定成果",
        "Excel预定成果 + AI确认",
        "大纲导入",
        "excel",
        "import",
        "batch_import",
    ),
    UNKNOWN: (UNKNOWN, "unknown", "未知", "无", "none"),
}


def normalize(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return UNKNOWN
    return _ALIASES.get(raw, raw if raw in _LABELS else UNKNOWN)


def is_manual(value: str | None) -> bool:
    return normalize(value) == MANUAL


def is_voice(value: str | None) -> bool:
    return normalize(value) == VOICE


def is_meeting(value: str | None) -> bool:
    return normalize(value) == MEETING


def is_ai_extract(value: str | None) -> bool:
    return normalize(value) == AI_EXTRACT


def is_import(value: str | None) -> bool:
    return normalize(value) == IMPORT


def label(value: str | None) -> str:
    return _LABELS.get(normalize(value), _LABELS[UNKNOWN])


def aliases_for(value: str | None) -> tuple[str, ...]:
    return _ALIASES_BY_KEY.get(normalize(value), (normalize(value),))
