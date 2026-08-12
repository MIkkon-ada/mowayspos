"""Runtime support for meeting-minute Skills that require clarification.

The runtime deliberately does not generate meeting content during preflight.
It only freezes inputs, runs deterministic Skill checks and persists questions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app import models
from app.services.meeting_skill_registry import (
    SkillPreflightInput,
    preflight_skill,
    route_meeting_skill,
)


class BlockingClarificationsError(RuntimeError):
    """Raised when somebody tries to run before blocking facts are resolved."""

    def __init__(self, questions: Iterable[models.MeetingSkillClarification]):
        self.questions = list(questions)
        super().__init__("存在尚未处置的阻断澄清项，暂不能生成会议纪要")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _snapshot_hash(transcript_text: str, reference_files: list[dict[str, Any]]) -> str:
    payload = _json({"transcript_text": transcript_text, "reference_files": reference_files})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _current_snapshot(
    db: Session, run: models.MeetingSkillRun
) -> models.MeetingSkillInputSnapshot:
    snapshot = db.get(models.MeetingSkillInputSnapshot, run.current_input_snapshot_id)
    if snapshot is None:
        raise ValueError("Skill Run 缺少当前输入快照")
    return snapshot


def _active_questions(
    db: Session, run: models.MeetingSkillRun
) -> list[models.MeetingSkillClarification]:
    return (
        db.query(models.MeetingSkillClarification)
        .filter(
            models.MeetingSkillClarification.run_id == run.id,
            models.MeetingSkillClarification.input_snapshot_id == run.current_input_snapshot_id,
        )
        .order_by(models.MeetingSkillClarification.id)
        .all()
    )


def _unresolved_blocking_questions(
    db: Session, run: models.MeetingSkillRun
) -> list[models.MeetingSkillClarification]:
    return [
        question
        for question in _active_questions(db, run)
        if question.blocking and question.resolved_at is None
    ]


def _validate_question(question: models.MeetingSkillClarification) -> None:
    if question.blocking and not question.required:
        raise ValueError("阻断澄清项必须同时标记为 required")
    if question.action == "material_upload" and question.answer_mode is not None:
        raise ValueError("补充材料项不应使用普通问答 answer_mode")


def _create_snapshot(
    db: Session,
    run: models.MeetingSkillRun,
    transcript_text: str,
    reference_files: list[dict[str, Any]],
) -> models.MeetingSkillInputSnapshot:
    for old_snapshot in (
        db.query(models.MeetingSkillInputSnapshot)
        .filter(
            models.MeetingSkillInputSnapshot.run_id == run.id,
            models.MeetingSkillInputSnapshot.is_current.is_(True),
        )
        .all()
    ):
        old_snapshot.is_current = False

    latest_version = (
        db.query(models.MeetingSkillInputSnapshot.version)
        .filter(models.MeetingSkillInputSnapshot.run_id == run.id)
        .order_by(models.MeetingSkillInputSnapshot.version.desc())
        .first()
    )
    snapshot = models.MeetingSkillInputSnapshot(
        run_id=run.id,
        version=(latest_version[0] + 1) if latest_version else 1,
        transcript_text=transcript_text or "",
        reference_files_json=_json(reference_files),
        input_hash=_snapshot_hash(transcript_text or "", reference_files),
        is_current=True,
    )
    db.add(snapshot)
    db.flush()
    run.current_input_snapshot_id = snapshot.id
    return snapshot


def _run_preflight(
    db: Session, run: models.MeetingSkillRun
) -> models.MeetingSkillRun:
    """Persist deterministic questions only. It never creates meeting output."""
    snapshot = _current_snapshot(db, run)
    skill = route_meeting_skill(run.skill_name)
    reference_files = json.loads(snapshot.reference_files_json or "[]")
    result = preflight_skill(
        skill,
        SkillPreflightInput(
            transcript_text=snapshot.transcript_text,
            reference_files=reference_files,
        ),
    )

    run.status = "preflighting"
    run.output_json = "{}"
    run.output_answer_revisions_json = "{}"
    db.flush()

    for draft in result.questions:
        question = models.MeetingSkillClarification(
            run_id=run.id,
            input_snapshot_id=snapshot.id,
            code=draft.code,
            question=draft.question,
            question_kind=draft.question_kind,
            blocking=draft.blocking,
            required=draft.required,
            action=draft.action,
            answer_mode=draft.answer_mode,
            allow_other=draft.allow_other,
            allow_omit=draft.allow_omit,
            options_json=_json(draft.options),
            evidence_json=_json(draft.evidence),
        )
        _validate_question(question)
        db.add(question)

    db.flush()
    run.status = "waiting_for_answers" if _unresolved_blocking_questions(db, run) else "running"
    return run


def start_preflight(
    db: Session,
    *,
    project_id: int,
    created_by_person_id: int | None,
    meeting_type: str,
    transcript_text: str,
    reference_files: list[dict[str, Any]],
) -> models.MeetingSkillRun:
    skill = route_meeting_skill(meeting_type, transcript_text)
    run = models.MeetingSkillRun(
        project_id=project_id,
        created_by_person_id=created_by_person_id,
        skill_name=skill.name if skill else "generic-meeting-minutes",
        skill_version=skill.version if skill else "1",
        status="created",
    )
    db.add(run)
    db.flush()
    _create_snapshot(db, run, transcript_text, reference_files)
    _run_preflight(db, run)
    db.commit()
    db.refresh(run)
    return run


def append_input_snapshot(
    db: Session,
    run: models.MeetingSkillRun,
    *,
    transcript_text: str,
    reference_files: list[dict[str, Any]],
) -> models.MeetingSkillRun:
    """Keep old material snapshots for audit, and preflight only the new snapshot."""
    _create_snapshot(db, run, transcript_text, reference_files)
    _run_preflight(db, run)
    db.commit()
    db.refresh(run)
    return run


def submit_answers(
    db: Session,
    run: models.MeetingSkillRun,
    *,
    answers: list[dict[str, Any]],
    answered_by_person_id: int | None,
) -> models.MeetingSkillRun:
    questions = {question.id: question for question in _active_questions(db, run)}
    for answer in answers:
        question = questions.get(answer.get("question_id"))
        if question is None:
            raise ValueError("澄清项不属于当前输入快照")
        _validate_question(question)

        omit = bool(answer.get("omit", False))
        if omit and not question.allow_omit:
            raise ValueError("该澄清项不能选择不写入纪要")
        if question.action == "material_upload":
            raise ValueError("补充材料需创建新的输入快照，不能作为普通答案提交")
        if not omit and answer.get("value") in (None, "", []):
            raise ValueError("请明确处置该澄清项")

        latest = (
            db.query(models.MeetingSkillClarificationAnswerRevision.answer_revision)
            .filter(models.MeetingSkillClarificationAnswerRevision.question_id == question.id)
            .order_by(models.MeetingSkillClarificationAnswerRevision.answer_revision.desc())
            .first()
        )
        answer_value = {"omit": True} if omit else {"value": answer.get("value")}
        db.add(
            models.MeetingSkillClarificationAnswerRevision(
                question_id=question.id,
                answer_revision=(latest[0] + 1) if latest else 1,
                answer_json=_json(answer_value),
                answered_by_person_id=answered_by_person_id,
            )
        )
        question.resolved_at = datetime.now(timezone.utc)

    if answers:
        # A newer answer revision invalidates any output generated from an older one.
        # The caller must explicitly resume the run to build a new reviewable result.
        run.output_json = "{}"
        run.output_answer_revisions_json = "{}"
        run.status = "waiting_for_answers" if _unresolved_blocking_questions(db, run) else "running"
    db.commit()
    db.refresh(run)
    return run


def _build_resolved_facts(db: Session, run: models.MeetingSkillRun) -> list[models.MeetingSkillResolvedFact]:
    facts: list[models.MeetingSkillResolvedFact] = []
    for question in _active_questions(db, run):
        latest = (
            db.query(models.MeetingSkillClarificationAnswerRevision)
            .filter(models.MeetingSkillClarificationAnswerRevision.question_id == question.id)
            .order_by(models.MeetingSkillClarificationAnswerRevision.answer_revision.desc())
            .first()
        )
        if latest is None:
            continue
        fact = (
            db.query(models.MeetingSkillResolvedFact)
            .filter(
                models.MeetingSkillResolvedFact.run_id == run.id,
                models.MeetingSkillResolvedFact.field_name == question.code,
            )
            .one_or_none()
        )
        if fact is None:
            fact = models.MeetingSkillResolvedFact(run_id=run.id, field_name=question.code)
            db.add(fact)
        value = json.loads(latest.answer_json)
        fact.value_json = latest.answer_json
        fact.display_value = "不写入纪要" if value.get("omit") else str(value.get("value", ""))
        fact.source_type = "recorder_answer"
        fact.evidence_json = question.evidence_json
        fact.answer_revision_id = latest.id
        facts.append(fact)
    db.flush()
    return facts


def resume_run(db: Session, run: models.MeetingSkillRun) -> models.MeetingSkillRun:
    blocked = _unresolved_blocking_questions(db, run)
    if blocked:
        raise BlockingClarificationsError(blocked)

    run.status = "running"
    facts = _build_resolved_facts(db, run)
    run.output_json = _json(
        {
            "skill_name": run.skill_name,
            "input_snapshot_id": run.current_input_snapshot_id,
            "resolved_facts": [fact.field_name for fact in facts],
        }
    )
    run.output_answer_revisions_json = _json(
        {fact.field_name: fact.answer_revision_id for fact in facts}
    )
    run.status = "ready_for_review"
    db.commit()
    db.refresh(run)
    return run
