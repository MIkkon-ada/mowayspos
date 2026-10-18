"""Identity-safe, authorized projection for the personal task center."""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import crud, models
from ..domain import project_lifecycle as PL
from ..permissions import get_user_context_from_db
from .project_access import resolve_visible_project_ids


def list_my_tasks(current_user: str, db: Session) -> dict:
    """Return active-scope tasks for the person bound to the authenticated account.

    Stable person IDs are authoritative. A legacy display-name match is accepted
    only when exactly one active person has that name; ambiguous rows are counted
    and withheld for manual reconciliation.
    """
    account = (
        db.query(models.Account)
        .filter_by(username=current_user, status="active")
        .first()
    )
    if account is None or account.person_id is None:
        from fastapi import HTTPException

        raise HTTPException(409, "当前账号未关联有效人员，无法汇总个人任务。")

    person = db.get(models.Person, account.person_id)
    if person is None or not person.is_active:
        from fastapi import HTTPException

        raise HTTPException(409, "当前账号关联的人员已停用，无法汇总个人任务。")

    context = get_user_context_from_db(current_user, db)
    visible_ids = resolve_visible_project_ids(context, db, allow_legacy=True)
    project_query = db.query(models.Project).filter(
        models.Project.status.in_((PL.S_ACTIVE, PL.S_PENDING_KICKOFF))
    )
    if visible_ids is not None:
        if not visible_ids:
            return {"projects": [], "tasks": [], "ambiguous_assignment_count": 0}
        project_query = project_query.filter(models.Project.id.in_(visible_ids))

    projects = project_query.order_by(models.Project.sort_order, models.Project.id).all()
    project_by_id = {project.id: project for project in projects}
    if not project_by_id:
        return {"projects": [], "tasks": [], "ambiguous_assignment_count": 0}

    person_name = (person.name or "").strip()
    matching_active_people = (
        db.query(func.count(models.Person.id))
        .filter(
            models.Person.name == person_name,
            models.Person.is_active.is_(True),
        )
        .scalar()
        if person_name
        else 0
    )
    legacy_name_is_unique = matching_active_people == 1

    assignment_filter = models.SubTask.assignee_id == person.id
    if legacy_name_is_unique:
        assignment_filter = or_(
            assignment_filter,
            (models.SubTask.assignee_id.is_(None))
            & (models.SubTask.assignee == person_name),
        )

    base_query = (
        db.query(models.SubTask, models.Task)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
            models.Task.project_id.in_(project_by_id),
        )
    )

    ambiguous_assignment_count = 0
    if person_name and not legacy_name_is_unique:
        ambiguous_assignment_count = (
            base_query.filter(
                models.SubTask.assignee_id.is_(None),
                models.SubTask.assignee == person_name,
            )
            .with_entities(func.count(models.SubTask.id))
            .scalar()
            or 0
        )

    rows = (
        base_query.filter(assignment_filter)
        .order_by(models.Task.id.asc(), models.SubTask.created_at.asc(), models.SubTask.id.asc())
        .all()
    )
    task_payloads = []
    for subtask, task in rows:
        project = project_by_id.get(task.project_id)
        if project is None:
            continue
        payload = crud.to_dict(subtask)
        payload.update({
            "parent_key_task": task.key_task,
            "parent_task_id": task.id,
            "parent_project_id": project.id,
            "parent_special_project": project.name,
        })
        task_payloads.append(payload)

    return {
        "projects": [{"id": project.id, "name": project.name} for project in projects],
        "tasks": task_payloads,
        "ambiguous_assignment_count": int(ambiguous_assignment_count),
    }
