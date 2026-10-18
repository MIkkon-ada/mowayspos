"""Background execution and safe status summaries for project meeting Agents."""

from __future__ import annotations

import json
import logging
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..ai.contracts import AIInvocationContext, Capability
from ..ai.service import AIService
from ..database import SessionLocal
from .project_meeting_agent import (
    AgentModelResponse,
    MeetingAgentError,
    PROMPT_VERSION,
    run_project_meeting_agent,
)
from .project_meeting_agent_tools import ProjectMeetingAgentTools
from .project_meeting_minutes import normalize_project_meeting_agent_result
from .project_meeting_work_progress import build_word_work_progress_preview


logger = logging.getLogger("bowei.project_meeting_agent_processing")

def _json_value(value: str, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _persist_audit(
    run: models.ProjectMeetingRun,
    *,
    step_count: int = 0,
    model_code: str = "",
    invocation_log_ids: list[int] | None = None,
    trace: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    raw_responses: list[str] | None = None,
) -> None:
    run.step_count = step_count
    run.prompt_version = PROMPT_VERSION
    run.model_code = model_code
    run.invocation_log_ids_json = json.dumps(invocation_log_ids or [], ensure_ascii=False)
    run.raw_responses_json = json.dumps(raw_responses or [], ensure_ascii=False)
    # The prompt contract/version and events stay server-side in this audit blob;
    # the polling endpoint exposes counts only, never raw document/model content.
    run.tool_trace_json = json.dumps(
        {
            "prompt": PROMPT_VERSION,
            "trace": trace or [],
            "events": events or [],
        },
        ensure_ascii=False,
    )


def _failure_message(error: Exception) -> str:
    text = str(error).strip()
    return text or "会议纪要 Agent 分析失败，请检查模型配置或稍后重试。"


def _event_model_code(events: list[dict[str, Any]] | None) -> str:
    for event in reversed(events or []):
        model_code = event.get("model_code") if isinstance(event, dict) else ""
        if isinstance(model_code, str) and model_code:
            return model_code
    return ""


def _names(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _apply_meeting_input(normalized: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """Keep explicitly entered meeting metadata in the review draft."""
    standard = snapshot.get("standard_minutes")
    if isinstance(standard, dict) and standard.get("is_standard_minutes"):
        # For a recognized Word template, the submitted Word fields are authoritative.
        return
    meeting_input = snapshot.get("meeting_input")
    if not isinstance(meeting_input, dict):
        return
    draft = normalized.get("meeting_draft")
    if not isinstance(draft, dict):
        return
    evidence = normalized.get("meeting_info_evidence")
    for field in ("title", "meeting_date", "location", "host", "participants", "organizer", "copied_to"):
        value = meeting_input.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        draft[field] = [name.strip() for name in value.replace("，", "、").split("、") if name.strip()] if field in {"participants", "copied_to"} else value.strip()
        if isinstance(evidence, dict):
            evidence.pop(field, None)


def _source_evidence(document_text: str, *values: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    cursor = 0
    missing = False
    for value in values:
        value = str(value or "").strip()
        if not value or value == "\\":
            continue
        start = document_text.find(value, cursor)
        if start >= 0 and not any(span["quote"] == value for span in spans):
            spans.append({"quote": value, "char_start": start, "char_end": start + len(value)})
            cursor = start + len(value)
        elif start < 0:
            missing = True
    ready = bool(spans) and not missing
    return spans, {"state": "ready" if ready else "blocked", "errors": [] if ready else ["原文位置未找到"]}


def apply_standard_meeting_minutes(normalized: dict[str, Any], snapshot: dict[str, Any], document_text: str) -> None:
    """Preserve the submitted formal minutes while leaving project proposals intact."""
    standard = snapshot.get("standard_minutes")
    if not isinstance(standard, dict) or not standard.get("is_standard_minutes"):
        return
    draft = normalized.get("meeting_draft")
    if not isinstance(draft, dict):
        return
    for field in ("title", "meeting_date", "location", "meeting_type", "host", "organizer"):
        value = str(standard.get(field) or "").strip()
        if value:
            draft[field] = value
    for field in ("participants", "copied_to"):
        draft[field] = [part.strip() for part in str(standard.get(field) or "").replace("，", "、").split("、") if part.strip()]
    draft["summary"] = ""
    normalized["summary_evidence"] = {"evidence": [], "validation": {"state": "ready", "errors": []}}
    info_evidence: dict[str, Any] = {}
    for field in ("title", "meeting_date", "location", "meeting_type", "host", "organizer"):
        spans, validation = _source_evidence(document_text, str(draft.get(field) or ""))
        if spans:
            info_evidence[field] = {"evidence": spans, "validation": validation}
    for field in ("participants", "copied_to"):
        spans, validation = _source_evidence(document_text, str(standard.get(field) or ""))
        if spans:
            info_evidence[field] = {"evidence": spans, "validation": validation}
    normalized["meeting_info_evidence"] = info_evidence

    def fact(content: str, *, code: str = "", topic: str = "", owner: str = "", tracker: str = "", due_date: str = "", source_note: str = "") -> dict[str, Any]:
        spans, validation = _source_evidence(document_text, content, owner, tracker, due_date, source_note)
        return {
            "content": content, "code": code, "topic": topic, "owner": owner, "tracker": tracker,
            "due_date": due_date, "source_note": source_note,
            "confidence": 1.0, "needs_confirmation": validation["state"] != "ready",
            "evidence": spans, "validation": validation,
        }

    normalized["agenda_items"] = [fact(str(item)) for item in standard.get("agenda_items", []) if str(item).strip()]
    normalized["decisions"] = [
        fact(str(point), topic=str(section.get("title") or ""))
        for section in standard.get("discussion_sections", []) if isinstance(section, dict)
        for point in section.get("points", []) if str(point).strip()
    ]
    normalized["next_stage_work"] = [
        fact(
            str(row.get("会议安排事项") or "").strip(),
            code=str(row.get("编号") or "").strip(),
            owner=str(row.get("负责人") or "").strip(" \\"),
            tracker=str(row.get("追踪人") or "").strip(" \\"),
            due_date=str(row.get("完成时限") or "").strip(),
            source_note=str(row.get("来源/备注") or "").strip(),
        )
        for row in standard.get("current_action_items", []) if isinstance(row, dict) and row.get("会议安排事项")
    ]
    tracking = []
    for row in standard.get("prior_action_items", []):
        if not isinstance(row, dict) or not row.get("上周事项"):
            continue
        content = str(row.get("上周事项") or "").strip()
        owner = str(row.get("负责人") or "").strip()
        status = str(row.get("状态") or "").strip()
        progress = str(row.get("本周进展/说明") or "").strip()
        spans, validation = _source_evidence(document_text, content, owner, status, progress)
        tracking.append({
            "content": content, "code": str(row.get("编号") or "").strip(), "owner": owner, "status": status, "progress_note": progress,
            "confidence": 1.0, "needs_confirmation": validation["state"] != "ready",
            "evidence": spans, "validation": validation,
        })
    normalized["prior_action_tracking"] = tracking
    normalized["completed_items"] = []
    normalized["risks"] = []


def _analysis_index(normalized: dict[str, Any], name: str, identifier: str) -> dict[str, dict[str, Any]]:
    items = normalized.get(name)
    if not isinstance(items, list):
        return {}
    return {
        item[identifier]: item
        for item in items
        if isinstance(item, dict) and isinstance(item.get(identifier), str)
    }


def _frozen_parent_baseline(snapshot: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict) or workstream.get("id") != target.get("workstream_id"):
            continue
        for key_task in workstream.get("key_tasks", []):
            if isinstance(key_task, dict) and key_task.get("id") == target.get("key_task_id"):
                return {
                    "project_id": snapshot.get("project_id"),
                    "workstream_id": workstream["id"],
                    "key_task_id": key_task["id"],
                    "key_task": json.loads(json.dumps(key_task, ensure_ascii=False)),
                }
    return {}


def _frozen_target_schedule(snapshot: dict[str, Any], target: dict[str, Any]) -> dict[str, Any] | None:
    parent = _frozen_parent_baseline(snapshot, target)
    key_task = parent.get("key_task") if isinstance(parent.get("key_task"), dict) else {}
    for schedule in key_task.get("execution_schedules", []):
        if isinstance(schedule, dict) and schedule.get("id") == target.get("execution_schedule_id"):
            return schedule
    return None


def _trusted_analysis_changes(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    changes = normalized.get("proposed_changes")
    if not isinstance(changes, list):
        return []
    return [
        change for change in changes
        if isinstance(change, dict)
        and isinstance(change.get("validation"), dict)
        and change["validation"].get("state") == "ready"
    ]


def _proposal_lineage(
    change: dict[str, Any],
    *,
    facts: dict[str, dict[str, Any]],
    matches: dict[str, dict[str, Any]],
    deltas: dict[str, dict[str, Any]],
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str, float] | None:
    fact = facts.get(change.get("source_fact_id"))
    match = matches.get(change.get("source_match_id"))
    delta = deltas.get(change.get("source_delta_id"))
    target = change.get("target") if isinstance(change.get("target"), dict) else {}
    proposed = change.get("proposed") if isinstance(change.get("proposed"), dict) else {}
    field_sources = change.get("field_sources") if isinstance(change.get("field_sources"), dict) else {}
    if not fact or not match or not delta or not target or not proposed:
        return None

    meeting_evidence: dict[str, list[dict[str, Any]]] = {}
    for field_name, source in field_sources.items():
        if not isinstance(source, dict) or source.get("source_type") != "meeting_fact":
            continue
        field = (fact.get("fields") if isinstance(fact.get("fields"), dict) else {}).get(field_name)
        evidence = field.get("evidence") if isinstance(field, dict) else None
        if not isinstance(evidence, list) or not evidence:
            return None
        meeting_evidence[field_name] = evidence

    parent_baseline = _frozen_parent_baseline(snapshot, target)
    if not parent_baseline:
        return None
    if change.get("action") == "update_execution_schedule":
        schedule = _frozen_target_schedule(snapshot, target)
        if schedule is None:
            return None
        before_baseline = {field: schedule.get(field) for field in proposed}
        baseline_state = "existing_target"
    elif change.get("action") == "create_execution_schedule":
        before_baseline = {}
        baseline_state = "not_applicable_new_object"
    else:
        return None

    evidence = [span for spans in meeting_evidence.values() for span in spans]
    lineage = {
        "schema_version": 1,
        "action": change["action"],
        "target": target,
        "requires_confirmation": change.get("requires_confirmation"),
        "change_id": change.get("change_id"),
        "source_fact_id": change.get("source_fact_id"),
        "source_match_id": change.get("source_match_id"),
        "source_delta_id": change.get("source_delta_id"),
        "field_sources": field_sources,
        "meeting_evidence": meeting_evidence,
        "project_evidence": match.get("project_evidence", []),
        "delta": delta,
        "before_baseline": before_baseline,
        "baseline_state": baseline_state,
        "parent_baseline": parent_baseline,
        "owner_edit_history": [],
    }
    return lineage, evidence, str(delta.get("reasoning") or ""), float(match.get("confidence") or 0)


def _persist_word_progress_proposals(
    db: Session,
    run: models.ProjectMeetingRun,
    normalized: dict[str, Any],
    change_set: models.MeetingChangeSet,
) -> None:
    """Persist review choices for a complete standard Word analysis."""
    preview = normalized.get("work_progress_preview")
    if isinstance(preview, dict):
        for row in preview.get("rows", []):
            if not isinstance(row, dict) or not isinstance(row.get("proposed"), dict) or not row["proposed"]:
                continue
            key_task_id = row.get("key_task_id")
            if not isinstance(key_task_id, int):
                continue
            latest_event = (
                db.query(models.KeyTaskExecutionEvent)
                .filter(
                    models.KeyTaskExecutionEvent.key_task_id == key_task_id,
                    models.KeyTaskExecutionEvent.authority == "confirmed",
                    models.KeyTaskExecutionEvent.affects_current_progress.is_(True),
                )
                .order_by(models.KeyTaskExecutionEvent.effective_at.desc(), models.KeyTaskExecutionEvent.id.desc())
                .first()
            )
            evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
            errors = []
            for span in evidence:
                if not isinstance(span, dict):
                    errors.append("会议原文依据格式无效")
                    continue
                start, end, quote = span.get("char_start"), span.get("char_end"), span.get("quote")
                if not isinstance(start, int) or not isinstance(end, int) or not isinstance(quote, str) or run.document_text[start:end] != quote:
                    errors.append("会议原文依据与 Word 内容不一致")
            if not evidence:
                errors.append("缺少会议原文依据")
            before = {
                "event_id": latest_event.id if latest_event else None,
                "progress_summary": latest_event.progress_summary if latest_event else "",
                "next_step": latest_event.next_step if latest_event else "",
            }
            source_fact_ids = list(dict.fromkeys(
                fact_id for ids in row.get("field_fact_ids", {}).values() for fact_id in ids
            ))
            db.add(models.MeetingChangeProposal(
                change_set_id=change_set.id,
                action="confirm_work_progress",
                target_type="subtask",
                target_id=key_task_id,
                parent_workstream_id=row.get("workstream_id"),
                parent_subtask_id=key_task_id,
                before_json=json.dumps(before, ensure_ascii=False),
                proposed_json=json.dumps(row["proposed"], ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                reason="Word 会议事项关联到该关键任务，审核后同步进展与下一步计划",
                confidence=float(row.get("confidence") or 0),
                validation_json=json.dumps({"state": "blocked" if errors else "ready", "errors": errors}, ensure_ascii=False),
                lineage_json=json.dumps({
                    "schema_version": 1, "source_fact_ids": source_fact_ids,
                    "field_fact_ids": row.get("field_fact_ids", {}),
                    "related_facts": row.get("related_facts", []),
                    "baseline_event_id": before["event_id"],
                }, ensure_ascii=False),
                execution_status="pending",
            ))
        unlinked_source = _analysis_index(normalized, "meeting_facts", "fact_id")
        unlinked_source.update(_analysis_index(normalized, "unmatched_items", "fact_id"))
        unlinked_source.update(_analysis_index(normalized, "needs_confirmation", "fact_id"))
        tracking_by_content = {
            item.get("content"): item for item in normalized.get("prior_action_tracking", [])
            if isinstance(item, dict) and isinstance(item.get("content"), str)
        }
        for item in preview.get("unlinked_facts", []):
            if not isinstance(item, dict):
                continue
            fact = unlinked_source.get(item.get("fact_id"))
            if not fact:
                continue
            content = str(fact.get("content") or "").strip()
            fact_type = str(fact.get("fact_type") or "")
            proposed: dict[str, str] = {}
            evidence = list(fact.get("meeting_evidence") or [])
            if fact_type == "action_item":
                proposed["next_step"] = content
            elif fact_type in {"progress", "completion", "output"}:
                tracked = tracking_by_content.get(content)
                value = str(tracked.get("progress_note") or "").strip() if tracked else content
                if value:
                    proposed["progress_summary"] = value
                    if tracked and value != content:
                        evidence.extend(span for span in tracked.get("evidence", [])
                                        if isinstance(span, dict) and span.get("quote") == value)
            db.add(models.MeetingChangeProposal(
                change_set_id=change_set.id,
                action="review_unlinked_fact",
                target_type="unresolved_fact",
                target_id=None,
                before_json=json.dumps(item, ensure_ascii=False),
                proposed_json=json.dumps(proposed, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                reason=str(item.get("reason") or ""),
                confidence=float(fact.get("confidence") or 0),
                validation_json=json.dumps({"state": "needs_review", "errors": ["请选择对应关键任务，或确认仅留在会议纪要"]}, ensure_ascii=False),
                lineage_json=json.dumps({"schema_version": 1, "source_fact_ids": [item["fact_id"]],
                                         "related_facts": [item], "review_decision": None}, ensure_ascii=False),
                execution_status="pending",
            ))


def _repair_legacy_standard_match_evidence(normalized: dict[str, Any], snapshot: dict[str, Any]) -> int:
    """Correct the old compact compiler's omitted object IDs when the frozen value agrees."""
    objects: dict[str, dict[str, Any]] = {}
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict):
            continue
        objects[f"workstream:{workstream.get('id')}"] = workstream
        for key_task in workstream.get("key_tasks", []):
            if not isinstance(key_task, dict):
                continue
            objects[f"key_task:{key_task.get('id')}"] = key_task
            for schedule in key_task.get("execution_schedules", []):
                if isinstance(schedule, dict):
                    objects[f"execution_schedule:{schedule.get('id')}"] = schedule
    repaired = 0
    for match in normalized.get("project_matches", []):
        if not isinstance(match, dict):
            continue
        validation = match.get("validation") or {}
        if validation.get("state") == "ready":
            continue
        if validation.get("errors") != ["project evidence must exactly reference a frozen snapshot field"]:
            raise ValueError("legacy match has a different validation error")
        target = match.get("target") or {}
        source_object = f"{target.get('target_type')}:{target.get('target_id')}"
        frozen = objects.get(source_object)
        proofs = match.get("project_evidence") or []
        if not frozen or not proofs:
            raise ValueError("legacy match target is missing from the frozen snapshot")
        for proof in proofs:
            if (not isinstance(proof, dict) or proof.get("source_object") != target.get("target_type")
                    or proof.get("field") not in frozen or proof.get("value") != frozen[proof["field"]]):
                raise ValueError("legacy match evidence differs from the frozen snapshot")
            proof["source_object"] = source_object
        match["validation"] = {"state": "ready", "errors": []}
        repaired += 1
    ready_matches = {
        match.get("match_id") for match in normalized.get("project_matches", [])
        if isinstance(match, dict) and (match.get("validation") or {}).get("state") == "ready"
    }
    for delta in normalized.get("project_deltas", []):
        if not isinstance(delta, dict):
            continue
        validation = delta.get("validation") or {}
        if validation.get("state") == "ready":
            continue
        if (validation.get("errors") != ["delta source_match_id is not a ready project match"]
                or delta.get("source_match_id") not in ready_matches):
            raise ValueError("legacy delta has a different validation error")
        delta["validation"] = {"state": "ready", "errors": []}
    return repaired


def backfill_standard_word_progress_review(db: Session, run_id: int) -> dict[str, int]:
    """Upgrade an untouched, pending Word review using its existing verified facts."""
    run = db.get(models.ProjectMeetingRun, run_id)
    if run is None or run.status != "pending_review":
        raise ValueError("meeting analysis is not pending review")
    latest_run = (db.query(models.ProjectMeetingRun)
                  .filter_by(document_source_id=run.document_source_id)
                  .order_by(models.ProjectMeetingRun.id.desc()).first())
    if latest_run is None or latest_run.id != run.id:
        raise ValueError("meeting analysis has a newer run")
    snapshot = _json_value(run.snapshot_json, {})
    standard = snapshot.get("standard_minutes")
    if not isinstance(standard, dict) or not standard.get("is_standard_minutes"):
        raise ValueError("meeting source is not a recognized standard Word")
    source = db.get(models.MeetingDocumentSource, run.document_source_id)
    meeting = db.get(models.Meeting, source.meeting_id) if source and source.meeting_id else None
    if (meeting is None or meeting.review_status != "pending_review"
            or meeting.publish_status != "draft" or meeting.review_version != 1):
        raise ValueError("meeting draft was already reviewed or changed")
    if db.query(models.MeetingReviewEvent.id).filter_by(meeting_id=meeting.id, action="edited").first():
        raise ValueError("meeting draft has human edits")
    change_set = (db.query(models.MeetingChangeSet).filter_by(meeting_id=meeting.id)
                  .order_by(models.MeetingChangeSet.id.desc()).first())
    if change_set is None:
        raise ValueError("meeting review package is missing")
    existing = (db.query(models.MeetingChangeProposal.id)
                .filter(models.MeetingChangeProposal.change_set_id == change_set.id,
                        models.MeetingChangeProposal.action.in_(("confirm_work_progress", "review_unlinked_fact")))
                .first())
    if existing:
        raise ValueError("work progress review already exists")
    normalized = _json_value(run.result_json, {})
    if "work_progress_preview" in normalized:
        raise ValueError("work progress preview already exists")
    repaired_matches = _repair_legacy_standard_match_evidence(normalized, snapshot)
    normalized["work_progress_preview"] = build_word_work_progress_preview(normalized, snapshot)
    _persist_word_progress_proposals(db, run, normalized, change_set)
    serialized = json.dumps(normalized, ensure_ascii=False)
    run.result_json = serialized
    change_set.result_json = serialized
    if repaired_matches:
        db.add(models.MeetingReviewEvent(
            meeting_id=meeting.id,
            action="analysis_repaired",
            actor_person_id=run.created_by_person_id,
            reason=f"Corrected {repaired_matches} compact Word match evidence identifiers against the frozen snapshot",
        ))
    db.flush()
    preview = normalized["work_progress_preview"]
    return {
        "matched_tasks": len(preview["rows"]),
        "unlinked_facts": len(preview["unlinked_facts"]),
        "proposals": db.query(models.MeetingChangeProposal).filter_by(change_set_id=change_set.id).count(),
        "repaired_matches": repaired_matches,
    }


def _create_review_draft(
    db: Session,
    run: models.ProjectMeetingRun,
    normalized: dict[str, Any],
    *,
    result_json: str,
) -> None:
    """Persist a reviewable meeting draft and proposals, never live plan changes."""
    draft = normalized.get("meeting_draft") if isinstance(normalized.get("meeting_draft"), dict) else {}
    meeting_type = str(draft.get("meeting_type") or "").strip()
    source = db.get(models.MeetingDocumentSource, run.document_source_id)
    meeting_values = {
        "project_id": run.project_id,
        "creator_person_id": run.created_by_person_id,
        "meeting_type": meeting_type,
        "title": str(draft.get("title") or (source.original_name if source else "会议纪要")).strip(),
        "meeting_date": str(draft.get("meeting_date") or "").strip(),
        "location": str(draft.get("location") or "").strip(),
        "host": str(draft.get("host") or "").strip(),
        "participants": _names(draft.get("participants")),
        "organizer": str(draft.get("organizer") or "").strip(),
        "copied_to": _names(draft.get("copied_to")),
        "agenda_items_json": json.dumps(normalized.get("agenda_items", []), ensure_ascii=False),
        "source_mode": "ai_analysis",
        "transcript_text": run.document_text,
        "summary": str(draft.get("summary") or "").strip(),
        "task_list_json": json.dumps(normalized.get("next_stage_work", []), ensure_ascii=False),
        "prior_action_items_json": json.dumps(normalized.get("prior_action_tracking", []), ensure_ascii=False),
        "decision_items_json": json.dumps(normalized.get("decisions", []), ensure_ascii=False),
        "risk_items_json": json.dumps(normalized.get("risks", []), ensure_ascii=False),
        "publish_status": "draft",
        "document_source_id": run.document_source_id,
        "review_status": "pending_review",
    }
    meeting = db.get(models.Meeting, source.meeting_id) if source and source.meeting_id else None
    if meeting is not None:
        if (
            meeting.document_source_id != run.document_source_id
            or meeting.review_status != "pending_review"
            or meeting.publish_status != "draft"
            or meeting.review_version != 1
        ):
            raise ValueError("已有会议草稿已进入人工修改或发布状态，拒绝用重跑结果覆盖")
        for key, value in meeting_values.items():
            setattr(meeting, key, value)
    else:
        meeting = models.Meeting(**meeting_values, review_version=1)
        db.add(meeting)
        db.flush()
    if source is not None:
        source.meeting_id = meeting.id

    change_set = models.MeetingChangeSet(
        project_id=run.project_id,
        meeting_id=meeting.id,
        created_by_person_id=run.created_by_person_id,
        transcript_hash=hashlib.sha256(run.document_text.encode("utf-8")).hexdigest(),
        snapshot_json=run.snapshot_json,
        result_json=result_json,
        status="draft",
    )
    db.add(change_set)
    db.flush()
    snapshot = _json_value(run.snapshot_json, {})
    facts = _analysis_index(normalized, "meeting_facts", "fact_id")
    matches = _analysis_index(normalized, "project_matches", "match_id")
    deltas = _analysis_index(normalized, "project_deltas", "delta_id")
    for change in _trusted_analysis_changes(normalized):
        persisted = _proposal_lineage(
            change, facts=facts, matches=matches, deltas=deltas, snapshot=snapshot,
        )
        if persisted is None:
            continue
        lineage, evidence, reason, confidence = persisted
        target = lineage["target"]
        db.add(models.MeetingChangeProposal(
            change_set_id=change_set.id,
            action=str(change.get("action") or ""),
            target_type="execution_schedule",
            target_id=target.get("execution_schedule_id"),
            parent_workstream_id=target.get("workstream_id"),
            parent_subtask_id=target.get("key_task_id"),
            before_json=json.dumps(change.get("before", {}), ensure_ascii=False),
            proposed_json=json.dumps(change.get("proposed", {}), ensure_ascii=False),
            evidence_json=json.dumps(evidence, ensure_ascii=False),
            reason=reason,
            confidence=confidence,
            validation_json=json.dumps(change.get("validation", {}), ensure_ascii=False),
            lineage_json=json.dumps(lineage, ensure_ascii=False),
            execution_status="pending",
        ))
    _persist_word_progress_proposals(db, run, normalized, change_set)
    db.add(models.MeetingReviewEvent(
        meeting_id=meeting.id,
        action="submitted",
        actor_person_id=run.created_by_person_id,
    ))


def process_project_meeting_agent_run(run_id: int, *, session_factory=SessionLocal) -> None:
    """Run one queued document in an independent database session.

    This function intentionally never creates a Meeting or change set.  The
    only permitted result is a verified, auditable pending-review run.
    """
    db: Session = session_factory()
    agent_result = None
    try:
        run = db.get(models.ProjectMeetingRun, run_id)
        if run is None or run.status != "queued":
            return

        run.status = "analyzing"
        run.stage = "understanding"
        db.commit()
        db.refresh(run)

        snapshot = _json_value(run.snapshot_json, {})
        if snapshot.get("project_id") != run.project_id:
            raise MeetingAgentError("project_boundary", "冻结项目上下文与任务项目不一致")

        tools = ProjectMeetingAgentTools(snapshot)

        def provider(prompt: str) -> AgentModelResponse:
            response = AIService(db).invoke_chat(
                Capability.MEETING_ANALYSIS,
                prompt,
                AIInvocationContext(resource_type="project_meeting_run", resource_id=run.id),
            )
            return AgentModelResponse(
                text=response.text,
                model_code=response.model_code,
                invocation_log_id=response.invocation_log_id,
                finish_reason=response.finish_reason,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )

        def on_event(event: dict[str, Any]) -> None:
            if event.get("kind") == "tool_result":
                run.stage = "matching"
                db.commit()

        agent_result = run_project_meeting_agent(
            project_id=run.project_id,
            document_text=run.document_text,
            snapshot=snapshot,
            tools=tools,
            provider=provider,
            on_event=on_event,
            require_plan_lookup=True,
        )
        run.stage = "validating"
        normalized = normalize_project_meeting_agent_result(agent_result.final, run.document_text, snapshot)
        apply_standard_meeting_minutes(normalized, snapshot, run.document_text)
        _apply_meeting_input(normalized, snapshot)
        if isinstance(snapshot.get("standard_minutes"), dict) and snapshot["standard_minutes"].get("is_standard_minutes"):
            normalized["work_progress_preview"] = build_word_work_progress_preview(normalized, snapshot)
        result_json = json.dumps(normalized, ensure_ascii=False)
        _create_review_draft(db, run, normalized, result_json=result_json)
        _persist_audit(
            run,
            step_count=agent_result.step_count,
            model_code=agent_result.model_code,
            invocation_log_ids=agent_result.invocation_log_ids,
            trace=agent_result.trace,
            events=agent_result.events,
            raw_responses=agent_result.raw_responses,
        )
        run.result_json = result_json
        run.status = "pending_review"
        run.stage = "pending_review"
        run.error_code = ""
        run.error_message = ""
        db.commit()
    except MeetingAgentError as exc:
        db.rollback()
        run = db.get(models.ProjectMeetingRun, run_id)
        if run is not None:
            _persist_audit(
                run,
                step_count=len(exc.raw_responses),
                model_code=_event_model_code(exc.events),
                invocation_log_ids=exc.invocation_log_ids,
                trace=exc.trace,
                events=exc.events,
                raw_responses=exc.raw_responses,
            )
            run.status = "failed"
            run.stage = "failed"
            run.error_code = exc.code
            run.error_message = _failure_message(exc)
            run.result_json = "{}"
            db.commit()
    except Exception as exc:  # keep infrastructure failures readable and auditable
        logger.exception("project meeting Agent run %s failed", run_id)
        db.rollback()
        run = db.get(models.ProjectMeetingRun, run_id)
        if run is not None:
            _persist_audit(
                run,
                step_count=agent_result.step_count if agent_result else 0,
                model_code=agent_result.model_code if agent_result else "",
                invocation_log_ids=agent_result.invocation_log_ids if agent_result else None,
                trace=agent_result.trace if agent_result else None,
                events=agent_result.events if agent_result else None,
                raw_responses=agent_result.raw_responses if agent_result else None,
            )
            run.status = "failed"
            run.stage = "failed"
            run.error_code = "processing_error"
            run.error_message = _failure_message(exc)
            run.result_json = "{}"
            db.commit()
    finally:
        db.close()


def project_meeting_run_status_payload(run: models.ProjectMeetingRun) -> dict[str, Any]:
    audit = _json_value(run.tool_trace_json, {})
    trace = audit.get("trace", []) if isinstance(audit, dict) else []
    events = audit.get("events", []) if isinstance(audit, dict) else []
    return {
        "id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "stage": run.stage,
        "step_count": run.step_count,
        "error_code": run.error_code or "",
        "error_message": run.error_message or "",
        "audit": {
            "model_code": run.model_code or "",
            "invocation_log_ids": _json_value(run.invocation_log_ids_json, []),
            "event_count": len(events) if isinstance(events, list) else 0,
            "tool_call_count": len(trace) if isinstance(trace, list) else 0,
        },
    }
