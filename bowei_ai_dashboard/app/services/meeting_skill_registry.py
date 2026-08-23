"""Skill routing and preflight contracts for meeting-minute agents.

This module is intentionally independent of HTTP and persistence.  Skills only
declare business eligibility and clarification drafts; the orchestration layer
owns run state, permissions, answers, and execution gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClarificationDraft:
    code: str
    question: str
    question_kind: str
    blocking: bool
    required: bool
    action: str = "answer"
    answer_mode: str | None = None
    allow_other: bool = False
    allow_omit: bool = False
    evidence: list[dict[str, Any]] = field(default_factory=list)
    options: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SkillPreflightInput:
    transcript_text: str
    reference_files: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SkillPreflightResult:
    can_run: bool
    questions: list[ClarificationDraft] = field(default_factory=list)


@dataclass(frozen=True)
class MeetingSkillDefinition:
    name: str
    version: str
    meeting_types: frozenset[str]


WEEKLY_RECEIVABLES_SKILL = MeetingSkillDefinition(
    name="weekly-meeting-minutes",
    version="1.3.5",
    meeting_types=frozenset({"receivables_weekly"}),
)


def route_meeting_skill(
    meeting_type: str | None,
    transcript_text: str | None = None,
) -> MeetingSkillDefinition | None:
    candidate = (meeting_type or "").strip()
    if candidate == "regular":
        return WEEKLY_RECEIVABLES_SKILL
    if candidate == WEEKLY_RECEIVABLES_SKILL.name or candidate in WEEKLY_RECEIVABLES_SKILL.meeting_types:
        return WEEKLY_RECEIVABLES_SKILL
    normalized_text = (transcript_text or "").lower()
    if ("验收" in normalized_text and "回款" in normalized_text) or (
        "acceptance" in normalized_text and "receivable" in normalized_text
    ):
        return WEEKLY_RECEIVABLES_SKILL
    return None


def _missing_material_question(kind: str, question: str) -> ClarificationDraft:
    return ClarificationDraft(
        code=f"{kind}_missing",
        question=question,
        question_kind="missing_material",
        blocking=True,
        required=True,
        action="material_upload",
        evidence=[{
            "source_type": "system_preflight",
            "source_id": "current_input_snapshot",
            "locator": f"required_reference:{kind}",
        }],
    )


def preflight_skill(
    skill: MeetingSkillDefinition | None,
    payload: SkillPreflightInput,
) -> SkillPreflightResult:
    """Perform deterministic input checks only; never generate minutes."""
    if skill is None:
        return SkillPreflightResult(can_run=True)

    supplied_kinds = {str(item.get("kind") or "") for item in payload.reference_files}
    questions: list[ClarificationDraft] = []
    if not payload.transcript_text.strip():
        questions.append(_missing_material_question("meeting_transcript", "请补充会议转写或可提取文字的会议文档。"))
    if "acceptance_receivables_ledger" not in supplied_kinds:
        questions.append(_missing_material_question("acceptance_receivables_ledger", "请补充最新验收/回款明细表。"))
    if "previous_minutes" not in supplied_kinds:
        questions.append(_missing_material_question("previous_minutes", "请补充上期会议纪要。"))
    return SkillPreflightResult(can_run=not questions, questions=questions)
