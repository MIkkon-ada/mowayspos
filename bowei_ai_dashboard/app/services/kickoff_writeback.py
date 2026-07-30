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
    if any(json.loads(item.validation_json or "[]") for item in proposals):
        raise HTTPException(409, "启动会提案包含未通过校验的内容")
    for proposal in proposals:
        _apply_approved_proposal(proposal, project.id, db)
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


def _apply_approved_proposal(proposal: models.KickoffChangeProposal, project_id: int, db: Session) -> None:
    """Apply only whitelisted fields on records that belong to this project."""
    values = json.loads(proposal.proposed_json or "{}")
    if not isinstance(values, dict):
        raise HTTPException(409, "启动会提案格式无效")
    if proposal.proposal_type == "create":
        if proposal.target_type != "subtask":
            raise HTTPException(409, "启动会只允许新增关键任务")
        task_id = values.get("task_id")
        parent = db.get(models.Task, task_id) if isinstance(task_id, int) else None
        if not parent or parent.project_id != project_id:
            raise HTTPException(409, "新增关键任务的重点工作不属于当前项目")
        title = values.get("title")
        assignee = values.get("assignee")
        if not isinstance(title, str) or not title.strip() or not isinstance(assignee, str) or not assignee.strip():
            raise HTTPException(409, "新增关键任务缺少标题或负责人")
        db.add(models.SubTask(
            task_id=parent.id,
            title=title.strip(),
            assignee=assignee.strip(),
            plan_time=str(values.get("plan_time") or "").strip(),
            status=str(values.get("status") or "未开始").strip(),
            completion_criteria=str(values.get("completion_criteria") or "").strip(),
            notes=str(values.get("notes") or "").strip(),
        ))
        return
    if proposal.proposal_type == "delete":
        if proposal.target_type == "task":
            row = db.get(models.Task, proposal.target_id)
            if not row or row.project_id != project_id:
                raise HTTPException(409, "删除提案目标不属于当前项目")
            row.is_deleted = True
            return
        if proposal.target_type == "subtask":
            row = db.get(models.SubTask, proposal.target_id)
            parent = db.get(models.Task, row.task_id) if row else None
            if not row or not parent or parent.project_id != project_id:
                raise HTTPException(409, "删除提案目标不属于当前项目")
            row.is_deleted = True
            return
        raise HTTPException(409, "删除提案目标类型无效")
    if proposal.proposal_type != "update" or proposal.target_id is None:
        return
    if proposal.target_type == "task":
        row = db.get(models.Task, proposal.target_id)
        allowed = {"key_task", "key_achievement", "completion_standard", "coordinator", "owner", "collaborators", "plan_time", "status", "problem_note"}
        if not row or row.project_id != project_id:
            raise HTTPException(409, "启动会提案目标不属于当前项目")
    elif proposal.target_type == "subtask":
        row = db.get(models.SubTask, proposal.target_id)
        parent = db.get(models.Task, row.task_id) if row else None
        allowed = {"title", "assignee", "plan_time", "status", "completion_criteria", "notes"}
        if not row or not parent or parent.project_id != project_id:
            raise HTTPException(409, "启动会提案目标不属于当前项目")
    else:
        return
    for key, value in values.items():
        if key in allowed and isinstance(value, str):
            setattr(row, key, value.strip())
