"""Read-only classification of legacy key tasks without stable assignee IDs."""

from __future__ import annotations

from .. import models
from sqlalchemy.orm import Session


def audit_unbound_task_assignees(db: Session) -> list[dict]:
    """Classify live subtasks with NULL assignee_id; never writes or repairs rows."""
    people_by_name: dict[str, list[int]] = {}
    for person_id, name in db.query(models.Person.id, models.Person.name).filter(
        models.Person.is_active.is_(True)
    ).all():
        normalized_name = (name or "").strip()
        if normalized_name:
            people_by_name.setdefault(normalized_name, []).append(person_id)

    rows = (
        db.query(models.SubTask, models.Task, models.Project)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .outerjoin(models.Project, models.Task.project_id == models.Project.id)
        .filter(
            models.SubTask.assignee_id.is_(None),
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
        )
        .order_by(models.Project.id, models.Task.id, models.SubTask.id)
        .all()
    )

    report = []
    for subtask, task, project in rows:
        assignee_name = (subtask.assignee or "").strip()
        candidate_ids = people_by_name.get(assignee_name, [])
        if len(candidate_ids) == 1:
            classification = "unique_candidate"
        elif len(candidate_ids) > 1:
            classification = "ambiguous"
        else:
            classification = "unmatched"
        report.append({
            "subtask_id": subtask.id,
            "project_id": project.id if project else task.project_id,
            "project_name": project.name if project else task.special_project or "",
            "workstream_id": task.id,
            "workstream_name": task.key_task or "",
            "title": subtask.title or "",
            "assignee_name": assignee_name,
            "classification": classification,
            "candidate_person_ids": candidate_ids,
        })
    return report
