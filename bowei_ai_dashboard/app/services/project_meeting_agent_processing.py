"""Background execution and safe status summaries for project meeting Agents."""

from __future__ import annotations

import json
import logging
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
        )
        run.stage = "validating"
        normalized = normalize_project_meeting_agent_result(agent_result.final, run.document_text, snapshot)
        _persist_audit(
            run,
            step_count=agent_result.step_count,
            model_code=agent_result.model_code,
            invocation_log_ids=agent_result.invocation_log_ids,
            trace=agent_result.trace,
            events=agent_result.events,
            raw_responses=agent_result.raw_responses,
        )
        run.result_json = json.dumps(normalized, ensure_ascii=False)
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
