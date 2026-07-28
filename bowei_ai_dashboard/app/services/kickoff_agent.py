"""Deterministic orchestration helpers for the kickoff-meeting Agent."""

from __future__ import annotations

from typing import Any

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
