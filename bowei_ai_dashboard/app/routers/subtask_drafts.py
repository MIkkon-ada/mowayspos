from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import (
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_role,
)
from ..services.notify import person_id_for_name as _pid_for_name
from ..time_utils import utc_now

router = APIRouter(prefix="/api/subtask-drafts", tags=["subtask-drafts"])


def _now() -> datetime:
    return utc_now()


def _draft_dict(draft: models.SubTaskDraft) -> dict:
    return crud.to_dict(draft)


def _draft_project_id(draft: models.SubTaskDraft, db: Session) -> int | None:
    if draft.project_id is not None:
        return draft.project_id
    if draft.parent_task_id:
        task = db.get(models.Task, draft.parent_task_id)
        if task and task.project_id is not None:
            return task.project_id
    return None


def _resolve_parent_task(draft: models.SubTaskDraft, payload_parent_task_id: int | None, db: Session) -> models.Task | None:
    task_id = payload_parent_task_id or draft.parent_task_id
    if not task_id:
        return None
    return db.get(models.Task, task_id)


@router.post("")
def create_drafts(
    payload: schemas.SubTaskDraftsPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_access(current_user, payload.project_id, db)

    created = []
    for item in payload.drafts:
        if not item.title.strip():
            continue
        if item.parent_task_id is not None:
            task = db.get(models.Task, item.parent_task_id)
            if not task:
                raise HTTPException(404, "parent task not found")
            if task.project_id is None:
                raise HTTPException(403, "permission denied")
            if task.project_id != payload.project_id:
                raise HTTPException(403, "permission denied")

        assignee = item.assignee or current_user
        draft = models.SubTaskDraft(
            project_id=payload.project_id,
            parent_task_id=item.parent_task_id,
            title=item.title.strip(),
            proposer=current_user,
            assignee=assignee,
            assignee_id=_pid_for_name(assignee, db),
            plan_time=item.plan_time or "",
            status="pending",
            source_submission_id=payload.source_submission_id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(draft)
        created.append(draft)

    db.commit()
    for row in created:
        db.refresh(row)
    return [_draft_dict(row) for row in created]


@router.get("")
def list_drafts(
    project_id: int | None = None,
    status: str = "pending",
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    is_admin = context.get("is_tech_admin", False)

    if project_id is not None:
        require_project_access(current_user, project_id, db)

    q = db.query(models.SubTaskDraft)
    if project_id is not None:
        q = q.filter(models.SubTaskDraft.project_id == project_id)
    if status != "all":
        q = q.filter(models.SubTaskDraft.status == status)
    q = q.order_by(models.SubTaskDraft.created_at.desc())
    rows = q.all()

    if not is_admin and project_id is None:
        rows = [row for row in rows if row.proposer == current_user or row.assignee == current_user]

    result = []
    for draft in rows:
        item = _draft_dict(draft)
        if draft.parent_task_id:
            task = db.get(models.Task, draft.parent_task_id)
            item["parent_task_title"] = task.key_task if task else ""
            item["parent_task_project"] = task.special_project if task else ""
        else:
            item["parent_task_title"] = ""
            item["parent_task_project"] = ""
        result.append(item)
    return result


@router.post("/{draft_id}/approve")
def approve_draft(
    draft_id: int,
    payload: schemas.SubTaskDraftApprovePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    draft = db.get(models.SubTaskDraft, draft_id)
    if not draft:
        raise HTTPException(404, "draft not found")
    if draft.status != "pending":
        raise HTTPException(400, f"draft is already {draft.status}")

    parent_task = _resolve_parent_task(draft, payload.parent_task_id, db)
    if not parent_task:
        raise HTTPException(422, "parent_task_id is required")

    project_id = _draft_project_id(draft, db)
    if project_id is not None:
        require_project_role(current_user, project_id, ["owner", "coordinator"], db)
    elif not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")

    assignee = payload.assignee or draft.assignee or draft.proposer
    subtask = models.SubTask(
        task_id=parent_task.id,
        title=draft.title,
        assignee=assignee,
        assignee_id=_pid_for_name(assignee, db),
        plan_time=payload.plan_time or draft.plan_time or "",
        status="未开始",
        source_submission_id=draft.source_submission_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(subtask)

    draft.status = "approved"
    draft.updated_at = _now()

    if subtask.assignee:
        from ..services.notify import send as _notify, person_name_for_account, person_id_for_name, person_id_for_account

        caller_name = person_name_for_account(current_user, db)
        caller_id = person_id_for_account(current_user, db)
        assignee_id = person_id_for_name(subtask.assignee, db)
        if subtask.assignee != current_user and subtask.assignee != caller_name and assignee_id != caller_id:
            _notify(
                db,
                recipient_id=assignee_id,
                recipient=subtask.assignee,
                ntype="subtask_assigned",
                title=f"New subtask: {subtask.title}",
                body=f"Task: {parent_task.key_task}; assigned by: {caller_name}",
                link=f"/project/{parent_task.project_id}/mytasks" if parent_task.project_id else "",
                project_id=parent_task.project_id,
            )

    db.commit()
    db.refresh(subtask)
    return {"ok": True, "subtask_id": subtask.id, "draft_id": draft_id}


@router.post("/{draft_id}/reject")
def reject_draft(
    draft_id: int,
    payload: schemas.SubTaskDraftRejectPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    draft = db.get(models.SubTaskDraft, draft_id)
    if not draft:
        raise HTTPException(404, "draft not found")
    if draft.status != "pending":
        raise HTTPException(400, f"draft is already {draft.status}")

    project_id = _draft_project_id(draft, db)
    if project_id is not None:
        require_project_role(current_user, project_id, ["owner", "coordinator"], db)
    elif not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")

    draft.status = "rejected"
    draft.reject_reason = payload.reason or ""
    draft.updated_at = _now()
    db.commit()
    return {"ok": True}


@router.delete("/{draft_id}")
def delete_draft(
    draft_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    draft = db.get(models.SubTaskDraft, draft_id)
    if not draft:
        raise HTTPException(404, "draft not found")

    project_id = _draft_project_id(draft, db)
    if project_id is None and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")
    if draft.proposer != current_user and not context.get("is_tech_admin"):
        raise HTTPException(403, "permission denied")

    db.delete(draft)
    db.commit()
    return {"ok": True}
