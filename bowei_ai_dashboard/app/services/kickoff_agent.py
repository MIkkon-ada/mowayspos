"""Deterministic orchestration helpers for the kickoff-meeting Agent."""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy.orm import Session

from .. import models


def build_kickoff_snapshot(project_id: int, db: Session) -> dict[str, Any]:
    """Freeze the plan the Agent is allowed to compare against."""
    tasks: list[dict[str, Any]] = []
    for task in db.query(models.Task).filter_by(project_id=project_id, is_deleted=False).order_by(models.Task.id).all():
        subtasks = db.query(models.SubTask).filter_by(task_id=task.id, is_deleted=False).order_by(models.SubTask.id).all()
        tasks.append({
            "id": task.id,
            "title": task.key_task,
            "owner": task.owner or "",
            "helper": task.collaborators or "",
            "plan_time": task.plan_time or "",
            "completion_standard": task.completion_standard or "",
            "subtasks": [{"id": row.id, "title": row.title, "assignee": row.assignee or "", "plan_time": row.plan_time or "", "completion_criteria": row.completion_criteria or ""} for row in subtasks],
        })
    return {"project_id": project_id, "tasks": tasks}


def normalize_agent_result(result: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Normalize untrusted model output into a review-only proposal package."""
    raw = result.get("proposals") if isinstance(result, dict) else None
    proposals = raw if isinstance(raw, list) else []
    normalized: list[dict[str, Any]] = []
    for item in proposals:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "proposal_type": str(item.get("proposal_type") or "update"),
            "target_type": str(item.get("target_type") or ""),
            "target_id": item.get("target_id"),
            "before": item.get("before") if isinstance(item.get("before"), dict) else {},
            "proposed": item.get("proposed") if isinstance(item.get("proposed"), dict) else {},
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            "validation_errors": [],
        })
    if not normalized:
        normalized = [{"proposal_type": "no_change", "evidence": []}]
        conclusion = "no_change"
    else:
        conclusion = "changes_proposed"
    return {"summary": str(result.get("summary") or ""), "snapshot": snapshot, "start_conclusion": conclusion, "proposals": normalized}


def validate_proposal(proposal: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    """Keep model suggestions within the immutable project plan snapshot."""
    target_type = proposal.get("target_type")
    target_id = proposal.get("target_id")
    if target_type not in {"task", "subtask"} or target_id is None:
        return []
    task_ids = {task.get("id") for task in snapshot.get("tasks", [])}
    subtask_ids = {
        subtask.get("id")
        for task in snapshot.get("tasks", [])
        for subtask in task.get("subtasks", [])
    }
    allowed = task_ids if target_type == "task" else subtask_ids
    if target_id not in allowed:
        return ["target_id does not belong to the frozen kickoff snapshot"]
    return []


def run_kickoff_agent(
    transcript: str,
    snapshot: dict[str, Any],
    provider: Callable[[str], dict[str, Any] | str],
) -> dict[str, Any]:
    """Ask the provider for review-only proposals and deterministically validate them."""
    prompt = (
        "Return JSON only with summary and proposals. Each proposal must include proposal_type, "
        "target_type, target_id, before, proposed, and evidence. Do not invent IDs.\n"
        f"Frozen plan: {json.dumps(snapshot, ensure_ascii=False)}\nMeeting transcript: {transcript}"
    )
    raw = provider(prompt)
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError("kickoff Agent returned an invalid JSON object")
    package = normalize_agent_result(raw, snapshot)
    for proposal in package["proposals"]:
        proposal["validation_errors"] = validate_proposal(proposal, snapshot)
    return package
