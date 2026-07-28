"""Atomic persistence for an approved kickoff review package."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..time_utils import utc_now


def confirm_kickoff_start(run_id: int, reviewer_name: str, db: Session):
    run = db.get(models.KickoffAgentRun, run_id)
    if not run:
        raise HTTPException(404, "启动会审核包不存在")
    project = db.get(models.Project, run.project_id)
    if not project or project.status != "pending_kickoff":
        raise HTTPException(409, "项目不处于待启动会状态")
    proposals = db.query(models.KickoffChangeProposal).filter_by(run_id=run.id).all()
    if any(item.review_status == "pending" for item in proposals):
        raise HTTPException(409, "启动会仍有未审核提案")
    if any(item.review_status == "returned" for item in proposals):
        raise HTTPException(409, "启动会提案已退回")
    data = json.loads(run.result_json or "{}")
    meeting = models.Meeting(project_id=project.id, meeting_type="kickoff", title="启动会纪要", summary=str(data.get("summary") or ""), publish_status="published")
    db.add(meeting)
    project.status = "active"
    project.is_active = True
    setattr(project, "lifecycle_status", "active")
    project.kickoff_date = utc_now().date().isoformat()
    project.kickoff_by = reviewer_name
    run.status = "approved"
    db.flush()
    return project, meeting
