from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..permissions import get_all_project_roles, get_current_user_name, get_user_context_from_db, require_login
from ..services.task_plan_proposals import apply_text_plan_proposals, create_text_plan_proposal_run


router = APIRouter(tags=["task-plan-proposals"])


def _json(value: str, fallback):
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed


def _key_task_for_write(key_task_id: int, current_user: str, db: Session):
    key_task = db.get(models.SubTask, key_task_id)
    task = db.get(models.Task, key_task.task_id) if key_task else None
    if not key_task or not task or key_task.is_deleted or task.is_deleted or not task.project_id:
        raise HTTPException(404, "关键任务不存在")
    context = get_user_context_from_db(current_user, db)
    person_id = context.get("person_id")
    can_write = bool(
        context.get("is_tech_admin")
        or context.get("name") == key_task.assignee
        or (person_id and set(get_all_project_roles(person_id, task.project_id, db)) & {"owner", "coordinator"})
    )
    if not can_write:
        raise HTTPException(403, "permission denied")
    return key_task, task, context


def _proposal_payload(row: models.TaskPlanProposal) -> dict:
    return {
        "id": row.id,
        "plan": _json(row.plan_json, {}),
        "evidence": _json(row.evidence_json, {}),
        "validation": _json(row.validation_json, {}),
        "status": row.status,
        "reviewer_edit": _json(row.reviewer_edit_json, {}),
        "created_plan_id": row.created_plan_id,
    }


def _run_payload(run: models.TaskPlanProposalRun, db: Session) -> dict:
    proposals = (
        db.query(models.TaskPlanProposal)
        .filter_by(run_id=run.id)
        .order_by(models.TaskPlanProposal.id.asc())
        .all()
    )
    return {
        "id": run.id,
        "project_id": run.project_id,
        "key_task_id": run.key_task_id,
        "status": run.status,
        "source_text": run.source_text,
        "model_code": run.model_code,
        "proposals": [_proposal_payload(row) for row in proposals],
    }


@router.post("/api/key-tasks/{key_task_id}/task-plan-proposal-runs", status_code=201)
def create_task_plan_proposal_run(
    key_task_id: int,
    payload: schemas.TaskPlanProposalTextCreatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    _, task, context = _key_task_for_write(key_task_id, current_user, db)
    run = create_text_plan_proposal_run(
        project_id=task.project_id,
        key_task_id=key_task_id,
        source_text=payload.source_text,
        created_by_person_id=context.get("person_id"),
        actor=current_user,
        db=db,
    )
    return _run_payload(run, db)


@router.get("/api/key-tasks/{key_task_id}/task-plan-proposal-runs/{run_id}")
def get_task_plan_proposal_run(
    key_task_id: int,
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    _, task, _ = _key_task_for_write(key_task_id, current_user, db)
    run = db.get(models.TaskPlanProposalRun, run_id)
    if not run or run.key_task_id != key_task_id or run.project_id != task.project_id:
        raise HTTPException(404, "计划草稿批次不存在")
    return _run_payload(run, db)


@router.patch("/api/task-plan-proposals/{proposal_id}")
def patch_task_plan_proposal(
    proposal_id: int,
    payload: schemas.TaskPlanProposalPatchPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    proposal = db.get(models.TaskPlanProposal, proposal_id)
    run = db.get(models.TaskPlanProposalRun, proposal.run_id) if proposal else None
    if not proposal or not run:
        raise HTTPException(404, "计划草稿不存在")
    _key_task_for_write(run.key_task_id, current_user, db)
    if proposal.status == "executed":
        raise HTTPException(409, "已创建的计划草稿不可编辑")
    try:
        validated = schemas.MonthPlanCreatePayload(**payload.plan)
    except Exception as exc:
        raise HTTPException(422, "计划草稿字段无效") from exc
    proposal.plan_json = json.dumps(validated.model_dump(mode="json"), ensure_ascii=False)
    proposal.reviewer_edit_json = json.dumps({"editor": current_user, "plan": validated.model_dump(mode="json")}, ensure_ascii=False)
    proposal.validation_json = json.dumps({"state": "ready", "errors": [], "reviewed": True}, ensure_ascii=False)
    proposal.status = "ready"
    db.commit()
    db.refresh(proposal)
    return _proposal_payload(proposal)


@router.post("/api/key-tasks/{key_task_id}/task-plan-proposal-runs/{run_id}/apply")
def apply_task_plan_proposal_run(
    key_task_id: int,
    run_id: int,
    payload: schemas.TaskPlanProposalApplyPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    _, task, context = _key_task_for_write(key_task_id, current_user, db)
    run = db.get(models.TaskPlanProposalRun, run_id)
    if not run or run.key_task_id != key_task_id or run.project_id != task.project_id:
        raise HTTPException(404, "计划草稿批次不存在")
    apply_text_plan_proposals(
        run=run,
        proposal_ids=payload.proposal_ids,
        actor=current_user,
        actor_person_id=context.get("person_id"),
        db=db,
    )
    db.refresh(run)
    return _run_payload(run, db)
