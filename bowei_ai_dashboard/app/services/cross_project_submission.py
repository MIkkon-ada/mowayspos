"""Atomic creation of project-scoped submissions from one reviewed report."""

from __future__ import annotations

import json
from collections import OrderedDict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..archived_guard import require_project_not_archived
from ..domain import source_type as ST
from ..domain import submission_status as SS
from ..permissions import get_user_context_from_db
from .notify import person_id_for_account, project_strict_owner_ids, send
from .policy import can_submit_to_project


def _existing_result(batch: models.UpdateSubmissionBatch, db: Session) -> dict:
    children = (
        db.query(models.UpdateSubmission)
        .filter(models.UpdateSubmission.batch_id == batch.id)
        .order_by(models.UpdateSubmission.batch_order, models.UpdateSubmission.id)
        .all()
    )
    return {"batch": batch, "submissions": children, "idempotent": True}


def _card_project(card: dict, index: int, db: Session) -> tuple[int, models.Task, models.SubTask]:
    try:
        parent_id = int(card.get("parent_task_id"))
        subtask_id = int(card.get("matched_subtask_id"))
    except (TypeError, ValueError):
        raise HTTPException(422, f"任务卡 {index + 1} 尚未完成归属")
    parent = db.get(models.Task, parent_id)
    subtask = db.get(models.SubTask, subtask_id)
    if not parent or parent.is_deleted or not parent.project_id:
        raise HTTPException(422, f"任务卡 {index + 1} 的重点工作无效")
    if not subtask or subtask.is_deleted or subtask.task_id != parent.id:
        raise HTTPException(422, f"任务卡 {index + 1} 的关键任务与重点工作不一致")
    return int(parent.project_id), parent, subtask


def _validate_project(project_id: int, context: dict, db: Session) -> models.Project:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(422, f"项目 {project_id} 不存在")
    if not can_submit_to_project(context, project_id, db):
        raise HTTPException(403, f"无权向项目「{project.name}」提交工作汇报")
    require_project_not_archived(project_id, db)
    if (project.status or "").strip().lower() != "active":
        raise HTTPException(409, f"项目「{project.name}」当前不可提交工作汇报")
    return project


def create_submission_batch(
    payload: schemas.BatchUpdateRequest,
    *,
    current_user: str,
    db: Session,
) -> dict:
    context = get_user_context_from_db(current_user, db)
    submitter_id = person_id_for_account(current_user, db) or context.get("person_id")
    if not submitter_id:
        raise HTTPException(401, "无法识别当前提交人")
    existing = (
        db.query(models.UpdateSubmissionBatch)
        .filter(models.UpdateSubmissionBatch.client_request_id == payload.client_request_id)
        .first()
    )
    if existing:
        if existing.submitter_id != submitter_id:
            raise HTTPException(409, "该请求标识已被其他提交使用")
        return _existing_result(existing, db)

    submitter = (context.get("name") or current_user).strip()
    reports = payload.human_result.get("task_reports")
    if not isinstance(reports, list) or not reports:
        raise HTTPException(422, "至少需要一张已确认归属的任务卡")

    grouped: OrderedDict[int, list[dict]] = OrderedDict()
    project_names: dict[int, str] = {}
    for index, raw_card in enumerate(reports):
        if not isinstance(raw_card, dict):
            raise HTTPException(422, f"任务卡 {index + 1} 格式无效")
        project_id, parent, subtask = _card_project(raw_card, index, db)
        project = _validate_project(project_id, context, db)
        card = dict(raw_card)
        card.update({
            "project_id": project_id,
            "project_name": project.name,
            "parent_task_id": parent.id,
            "parent_key_task": parent.key_task,
            "matched_subtask_id": subtask.id,
            "matched_subtask_title": subtask.title,
            "match_status": "matched",
        })
        grouped.setdefault(project_id, []).append(card)
        project_names[project_id] = project.name

    source_type = ST.normalize(payload.source_type)
    batch = models.UpdateSubmissionBatch(
        client_request_id=payload.client_request_id,
        submitter=submitter,
        submitter_id=submitter_id,
        source_type=source_type,
        title=payload.title or "工作汇报",
        transcript_text=payload.transcript_text,
        submission_count=len(grouped),
    )
    db.add(batch)
    db.flush()

    children: list[models.UpdateSubmission] = []
    for order, (project_id, cards) in enumerate(grouped.items()):
        scoped_result = dict(payload.human_result)
        scoped_result["task_reports"] = cards
        scoped_result["special_project"] = project_names[project_id]
        confidence_values = [float(card.get("match_confidence") or 0) for card in cards]
        row = models.UpdateSubmission(
            batch_id=batch.id,
            batch_order=order,
            project_id=project_id,
            source_type=source_type,
            submitter=submitter,
            submitter_id=submitter_id,
            title=payload.title or "工作汇报",
            transcript_text=payload.transcript_text,
            ai_result_json=json.dumps(scoped_result, ensure_ascii=False),
            human_result_json=json.dumps(scoped_result, ensure_ascii=False),
            confirm_status=SS.S_NEW,
            confidence=sum(confidence_values) / len(confidence_values) if confidence_values else 0,
        )
        db.add(row)
        db.flush()
        children.append(row)
        for owner_id in project_strict_owner_ids(project_id, db):
            if owner_id == submitter_id:
                continue
            send(
                db,
                recipient_id=owner_id,
                ntype="submission_pending",
                title="有新的提交待确认",
                body=f"{submitter} 提交了一条更新，请前往 AI 确认中心处理。",
                link=f"/work/confirmations?projectId={project_id}&submissionId={row.id}",
                project_id=project_id,
            )

    return {"batch": batch, "submissions": children, "idempotent": False}


def serialize_batch_result(result: dict) -> dict:
    return {
        "batch": crud.to_dict(result["batch"]),
        "submissions": [crud.to_dict(row) for row in result["submissions"]],
        "idempotent": bool(result.get("idempotent")),
    }
