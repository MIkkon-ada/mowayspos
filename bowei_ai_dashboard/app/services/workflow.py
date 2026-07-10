"""
UpdateSubmission state machine helpers and derived-entity write utilities.

Routers import from here instead of defining these inline.
"""
import json
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..domain import submission_status as SS


# ── Status helpers ────────────────────────────────────────────

def submission_status(row: models.UpdateSubmission) -> str:
    return SS.normalize(row.confirm_status)


def submission_result(row: models.UpdateSubmission) -> dict:
    """Best available result: human_result_json falling back to ai_result_json."""
    for field in (row.human_result_json, row.ai_result_json):
        if field:
            try:
                return json.loads(field)
            except Exception:
                pass
    return {}


def json_or_empty(value: str | None) -> dict:
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


def filtered_fields(model, data: dict) -> dict:
    """Keep only keys that exist as columns on the model and whose value isn't empty string."""
    return {k: v for k, v in data.items() if hasattr(model, k) and v != ""}


def require_submission_status(
    row: models.UpdateSubmission, allowed: set[str]
) -> None:
    if submission_status(row) not in allowed:
        raise HTTPException(409, "当前状态不允许执行该操作。")


def require_project_id(row: models.UpdateSubmission) -> None:
    if row.project_id is None:
        raise HTTPException(
            422,
            "该提交缺少项目归属（project_id=NULL），无法执行项目闭环操作。"
            "请先通过数据迁移脚本为历史数据补充 project_id 后再操作。",
        )


# ── Achievement fulfillment (shared by confirm endpoint) ──────

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


def find_planned_achievement(
    db: Session,
    item: dict,
    task_id: int | None,
    project: str,
) -> models.Achievement | None:
    query = db.query(models.Achievement).filter(
        models.Achievement.source_type == "Excel预定成果"
    )
    if task_id:
        query = query.filter(models.Achievement.related_task_id == task_id)
    elif project:
        query = query.filter(models.Achievement.special_project == project)
    candidates = query.all()
    if not candidates:
        return None
    name = item.get("name", "")
    best = max(candidates, key=lambda r: _similarity(name, r.name))
    return best if _similarity(name, best.name) >= 0.58 else None


def fulfill_or_create_achievement(
    db: Session,
    item: dict,
    source_type: str,
    task_id: int | None,
    project: str,
    *,
    submission_id: int | None = None,
) -> models.Achievement:
    planned = find_planned_achievement(db, item, task_id, project)
    clean = filtered_fields(models.Achievement, item)
    if planned:
        planned.status = (
            item.get("status") if item.get("status") and item.get("status") != "计划中"
            else "已形成"
        )
        planned.source_type = "Excel预定成果 + AI确认"
        planned.owner = item.get("owner") or planned.owner
        planned.version = item.get("version") or planned.version or "V0.1"
        planned.file_link = item.get("file_link") or planned.file_link
        planned.scenario = item.get("scenario") or planned.scenario
        planned.reuse_tag = item.get("reuse_tag") or planned.reuse_tag
        planned.achievement_type = item.get("achievement_type") or planned.achievement_type
        if submission_id is not None:
            planned.source_submission_id = submission_id
        return planned

    achievement = models.Achievement(**clean)
    achievement.related_task_id = clean.get("related_task_id") or task_id
    achievement.special_project = clean.get("special_project") or project
    achievement.status = clean.get("status") or "补充成果"
    achievement.source_type = source_type or "AI确认"
    if submission_id is not None:
        achievement.source_submission_id = submission_id
    db.add(achievement)
    return achievement
