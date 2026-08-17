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


logger = logging.getLogger("bowei.project_meeting_agent_processing")

_STANDARD_MEETING_TYPES = frozenset({
    "regular", "special", "kickoff", "communication", "review", "retrospective",
})


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


def _create_review_draft(
    db: Session,
    run: models.ProjectMeetingRun,
    normalized: dict[str, Any],
    *,
    result_json: str,
) -> None:
    """Persist a reviewable meeting draft and proposals, never live plan changes."""
    draft = normalized.get("meeting_draft") if isinstance(normalized.get("meeting_draft"), dict) else {}
    try:
        requested_meeting_type = str(json.loads(run.snapshot_json).get("requested_meeting_type") or "").strip()
    except (TypeError, ValueError, json.JSONDecodeError):
        requested_meeting_type = ""
    meeting_type = requested_meeting_type if requested_meeting_type in _STANDARD_MEETING_TYPES else str(draft.get("meeting_type") or "").strip()
    source = db.get(models.MeetingDocumentSource, run.document_source_id)
    meeting = models.Meeting(
        project_id=run.project_id,
        creator_person_id=run.created_by_person_id,
        meeting_type=meeting_type,
        title=str(draft.get("title") or (source.original_name if source else "会议纪要")).strip(),
        meeting_date=str(draft.get("meeting_date") or "").strip(),
        location=str(draft.get("location") or "").strip(),
        host=str(draft.get("host") or "").strip(),
        participants=_names(draft.get("participants")),
        organizer=str(draft.get("organizer") or "").strip(),
        copied_to=_names(draft.get("copied_to")),
        agenda_items_json=json.dumps(normalized.get("agenda_items", []), ensure_ascii=False),
        source_mode="ai_analysis",
        transcript_text=run.document_text,
        summary=str(draft.get("summary") or "").strip(),
        task_list_json=json.dumps(normalized.get("next_stage_work", []), ensure_ascii=False),
        decision_items_json=json.dumps(normalized.get("decisions", []), ensure_ascii=False),
        risk_items_json=json.dumps(normalized.get("risks", []), ensure_ascii=False),
        publish_status="draft",
        document_source_id=run.document_source_id,
        review_status="pending_review",
        review_version=1,
    )
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
            requested_meeting_type=str(snapshot.get("requested_meeting_type") or ""),
            on_event=on_event,
            require_plan_lookup=True,
        )
        run.stage = "validating"
        normalized = normalize_project_meeting_agent_result(agent_result.final, run.document_text, snapshot)
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
