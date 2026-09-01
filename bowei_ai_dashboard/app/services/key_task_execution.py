"""Confirmed Key Task execution projection and workspace domain rules."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..time_utils import utc_now


SOURCE_LABELS = {
    "update_submission": "个人提交",
    "meeting_progress_review": "会议确认",
    "key_task": "人工更新",
    "execution_schedule": "计划变更",
    "achievement": "成果",
    "issue": "问题",
    "task_plan_proposal": "AI 计划拆解",
}

PRESERVED_PLAN_STATUSES = {"已完成", "已取消", "暂缓", "延期", "已延期"}


def is_execution_plan_overdue(row: models.ExecutionSchedule, *, today: date | None = None) -> bool:
    today = today or utc_now().date()
    return bool(
        row.status not in PRESERVED_PLAN_STATUSES
        and (row.due_kind == "exact" or (not row.due_kind and row.due_date is not None))
        and row.due_date
        and row.due_date < today
    )


def execution_plan_display_status(row: models.ExecutionSchedule, *, today: date | None = None) -> str:
    today = today or utc_now().date()
    if row.status in PRESERVED_PLAN_STATUSES:
        return row.status
    if is_execution_plan_overdue(row, today=today):
        return "已延期"
    if row.start_date:
        return "未开始" if row.start_date > today else "进行中"
    return row.status


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def record_execution_event(
    db: Session,
    *,
    project_id: int,
    key_task_id: int,
    event_type: str,
    source_type: str,
    source_id: int,
    dedupe_key: str,
    actor_name: str,
    occurred_at: datetime,
    confirmed_at: datetime,
    effective_at: datetime,
    affects_current_progress: bool,
    actor_person_id: int | None = None,
    execution_plan_id: int | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    progress_summary: str | None = None,
    next_step: str | None = None,
    display_payload: dict[str, Any] | None = None,
    authority: str = "confirmed",
) -> models.KeyTaskExecutionEvent:
    """Add one immutable event, returning the existing row on an idempotent retry."""
    existing = (
        db.query(models.KeyTaskExecutionEvent)
        .filter(models.KeyTaskExecutionEvent.dedupe_key == dedupe_key)
        .first()
    )
    if existing:
        return existing
    row = models.KeyTaskExecutionEvent(
        project_id=project_id,
        key_task_id=key_task_id,
        execution_plan_id=execution_plan_id,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        dedupe_key=dedupe_key,
        actor_person_id=actor_person_id,
        actor_name_snapshot=(actor_name or "")[:100],
        occurred_at=occurred_at,
        confirmed_at=confirmed_at,
        effective_at=effective_at,
        affects_current_progress=bool(affects_current_progress),
        status_before=status_before,
        status_after=status_after,
        progress_summary=(progress_summary or "").strip() or None,
        next_step=(next_step or "").strip() or None,
        display_payload_json=(
            json.dumps(display_payload, ensure_ascii=False) if display_payload else None
        ),
        authority=authority,
        created_at=utc_now(),
    )
    db.add(row)
    db.flush()
    return row


def event_dict(row: models.KeyTaskExecutionEvent) -> dict[str, Any]:
    try:
        display_payload = json.loads(row.display_payload_json or "{}")
    except (TypeError, ValueError):
        display_payload = {}
    return {
        "id": row.id,
        "event_type": row.event_type,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "source_label": SOURCE_LABELS.get(row.source_type, row.source_type),
        "execution_plan_id": row.execution_plan_id,
        "actor": {
            "person_id": row.actor_person_id,
            "name": row.actor_name_snapshot or "",
        },
        "occurred_at": _iso(row.occurred_at),
        "confirmed_at": _iso(row.confirmed_at),
        "effective_at": _iso(row.effective_at),
        "affects_current_progress": bool(row.affects_current_progress),
        "status_before": row.status_before,
        "status_after": row.status_after,
        "progress_summary": row.progress_summary,
        "next_step": row.next_step,
        "display_payload": display_payload,
        "authority": row.authority,
    }


def current_progress_dict(db: Session, key_task_id: int) -> dict[str, Any] | None:
    row = (
        db.query(models.KeyTaskExecutionEvent)
        .filter(
            models.KeyTaskExecutionEvent.key_task_id == key_task_id,
            models.KeyTaskExecutionEvent.authority == "confirmed",
            models.KeyTaskExecutionEvent.affects_current_progress.is_(True),
        )
        .order_by(
            models.KeyTaskExecutionEvent.effective_at.desc(),
            models.KeyTaskExecutionEvent.id.desc(),
        )
        .first()
    )
    if not row:
        return None
    event = event_dict(row)
    return {
        "progress_summary": event["progress_summary"],
        "next_step": event["next_step"],
        "source_type": event["source_type"],
        "source_id": event["source_id"],
        "source_label": event["source_label"],
        "actor": event["actor"],
        "occurred_at": event["occurred_at"],
        "effective_at": event["effective_at"],
    }


def timeline_dicts(db: Session, key_task_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
    rows = (
        db.query(models.KeyTaskExecutionEvent)
        .filter(
            models.KeyTaskExecutionEvent.key_task_id == key_task_id,
            models.KeyTaskExecutionEvent.authority == "confirmed",
        )
        .order_by(
            models.KeyTaskExecutionEvent.occurred_at.desc(),
            models.KeyTaskExecutionEvent.id.desc(),
        )
        .limit(limit)
        .all()
    )
    legacy_batches: dict[tuple[Any, ...], list[models.KeyTaskExecutionEvent]] = {}
    for row in rows:
        if row.source_type != "task_plan_proposal" or row.event_type != "execution_plan_created":
            continue
        occurred_at = row.occurred_at
        if not occurred_at:
            continue
        batch_key = (
            row.actor_person_id,
            row.actor_name_snapshot,
            occurred_at.replace(second=0, microsecond=0),
        )
        legacy_batches.setdefault(batch_key, []).append(row)

    aggregated_ids: set[int] = set()
    timeline: list[dict[str, Any]] = []
    for row in rows:
        if row.source_type == "task_plan_proposal" and row.event_type == "execution_plan_created" and row.occurred_at:
            batch_key = (
                row.actor_person_id,
                row.actor_name_snapshot,
                row.occurred_at.replace(second=0, microsecond=0),
            )
            batch = legacy_batches[batch_key]
            if len(batch) > 1:
                if row.id in aggregated_ids:
                    continue
                aggregated_ids.update(item.id for item in batch)
                event = event_dict(row)
                event["event_type"] = "execution_plans_created"
                event["execution_plan_id"] = None
                event["progress_summary"] = f"AI 拆解已确认，新增 {len(batch)} 项任务计划"
                event["display_payload"] = {
                    "execution_plan_ids": [item.execution_plan_id for item in batch],
                    "plan_count": len(batch),
                }
                timeline.append(event)
                continue
        timeline.append(event_dict(row))
    return timeline


def effective_execution_plans(db: Session, key_task_id: int) -> list[models.ExecutionSchedule]:
    return (
        db.query(models.ExecutionSchedule)
        .filter(
            models.ExecutionSchedule.subtask_id == key_task_id,
            models.ExecutionSchedule.is_deleted.is_(False),
            models.ExecutionSchedule.is_archived.is_(False),
            models.ExecutionSchedule.status != "已取消",
        )
        .all()
    )


def plan_summary_dict(db: Session, key_task_id: int) -> dict[str, int]:
    rows = effective_execution_plans(db, key_task_id)
    statuses = [execution_plan_display_status(row) for row in rows]
    completed = sum(status == "已完成" for status in statuses)
    not_started = sum(status in {"待开始", "未开始"} for status in statuses)
    delayed = sum(status in {"延期", "已延期"} for status in statuses)
    return {
        "total": len(rows),
        "completed": completed,
        "in_progress": sum(status == "进行中" for status in statuses),
        "not_started": not_started,
        "delayed": delayed,
    }


def completion_eligibility_dict(db: Session, key_task_id: int) -> dict[str, Any]:
    summary = plan_summary_dict(db, key_task_id)
    if summary["total"] == 0:
        state = "no_execution_plan"
    elif summary["completed"] == summary["total"]:
        state = "eligible"
    else:
        state = "in_progress"
    return {
        "state": state,
        "effective_plan_count": summary["total"],
        "completed_plan_count": summary["completed"],
        "requires_owner_confirmation": state == "eligible",
    }


def due_display(
    *,
    due_kind: str | None,
    due_date: date | None,
    due_label: str | None,
) -> str:
    if due_kind == "exact" and due_date:
        return f"{due_date.month}/{due_date.day}"
    if due_kind == "fuzzy" and (due_label or "").strip():
        return (due_label or "").strip()
    return "暂未确定"


def normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
