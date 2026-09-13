from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain import source_type as ST


class ProjectPlanImportValidationError(ValueError):
    def __init__(self, errors: list[dict[str, object]]):
        self.errors = errors
        super().__init__("工作计划表存在无法导入的行")


def _text(value: str | None) -> str:
    return str(value or "").strip()


def _combine_plan_time(start: str | None, end: str | None) -> str:
    start_text = _text(start)
    end_text = _text(end)
    if start_text and end_text:
        return f"{start_text}~{end_text}"
    return start_text or end_text


def _split_names(value: str | None) -> list[str]:
    return [item.strip() for item in re.split(r"[/,、\\]+", _text(value)) if item.strip()]


def _person_id(name: str, db: Session) -> int | None:
    if not name:
        return None
    person = db.query(models.Person).filter(models.Person.name == name).first()
    return person.id if person else None


def _find_workstream(project_id: int, name: str, db: Session) -> models.Task | None:
    candidates = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    return next(
        (row for row in candidates if not bool(row.is_deleted) and _text(row.key_task) == name),
        None,
    )


def _find_key_task(task_id: int, title: str, db: Session) -> models.SubTask | None:
    candidates = db.query(models.SubTask).filter(models.SubTask.task_id == task_id).all()
    return next(
        (row for row in candidates if not bool(row.is_deleted) and _text(row.title) == title),
        None,
    )


def _validate_rows(rows: Iterable[schemas.BatchImportRow]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        project_name = _text(row.project_name)
        key_task = _text(row.key_task)
        workstream = _text(row.workstream) or key_task
        missing = []
        if not project_name:
            missing.append("项目")
        if not workstream:
            missing.append("重点工作")
        if not key_task:
            missing.append("关键任务")
        if missing:
            errors.append({"row": index, "message": f"缺少{'、'.join(missing)}"})
    return errors


def _subtask_notes(row: schemas.BatchImportRow) -> str:
    lines: list[str] = []
    collaborators = _text(row.collaborators)
    notes = _text(row.notes)
    if collaborators:
        lines.append(f"协同人：{collaborators}")
    if notes:
        lines.append(notes)
    return "\n".join(lines)


def _sync_active_lifecycle(project_id: int, db: Session) -> None:
    columns = {column["name"] for column in inspect(db.connection()).get_columns("projects")}
    if "lifecycle_status" in columns:
        db.execute(
            text("UPDATE projects SET lifecycle_status = :status WHERE id = :project_id"),
            {"status": "active", "project_id": project_id},
        )


def import_project_plan_rows(
    db: Session,
    rows: list[schemas.BatchImportRow],
    current_user: str,
) -> dict[str, int | bool]:
    errors = _validate_rows(rows)
    if errors:
        raise ProjectPlanImportValidationError(errors)

    projects_created = 0
    projects_matched = 0
    tasks_created = 0
    subtasks_created = 0
    issues_created = 0
    duplicates_skipped = 0
    project_cache: dict[str, models.Project] = {}
    task_cache: dict[tuple[int, str], models.Task] = {}

    try:
        for row in rows:
            project_name = _text(row.project_name)
            workstream_name = _text(row.workstream) or _text(row.key_task)
            key_task_name = _text(row.key_task)

            if project_name not in project_cache:
                project = db.query(models.Project).filter(models.Project.name == project_name).first()
                if project is None:
                    project = models.Project(
                        name=project_name,
                        objectives=_text(row.project_objective),
                        status="active",
                        is_active=True,
                        coordinator=_text(row.coordinator),
                        owners=_text(row.owner),
                        collaborators=_text(row.collaborators),
                    )
                    db.add(project)
                    db.flush()
                    _sync_active_lifecycle(project.id, db)
                    projects_created += 1
                    crud.log(db, current_user, "批量导入建项", "project", project.id, {}, {"name": project_name})
                else:
                    projects_matched += 1
                    if not _text(project.objectives) and _text(row.project_objective):
                        project.objectives = _text(row.project_objective)
                project_cache[project_name] = project

            project = project_cache[project_name]
            task_key = (project.id, workstream_name)
            task = task_cache.get(task_key) or _find_workstream(project.id, workstream_name, db)
            if task is None:
                task_plan_time = _combine_plan_time(
                    row.workstream_plan_start,
                    row.workstream_plan_end,
                ) or _text(row.plan_time)
                task = models.Task(
                    project_id=project.id,
                    special_project=project_name,
                    key_task=workstream_name[:200],
                    key_achievement=_text(row.key_achievement)[:200],
                    completion_standard=_text(row.completion_standard),
                    coordinator=_text(row.coordinator),
                    owner=_text(row.owner),
                    owner_id=_person_id(_text(row.owner), db),
                    collaborators=_text(row.collaborators),
                    plan_time=task_plan_time,
                    status=_text(row.status) or "未开始",
                    source_type=ST.normalize("批量导入"),
                    submitter=current_user,
                )
                db.add(task)
                db.flush()
                tasks_created += 1
                crud.log(db, current_user, "批量导入建重点工作", "task", task.id, {}, {"key_task": workstream_name})
            task_cache[task_key] = task

            if _find_key_task(task.id, key_task_name, db) is not None:
                duplicates_skipped += 1
                continue

            subtask = models.SubTask(
                task_id=task.id,
                title=key_task_name[:200],
                assignee=_text(row.owner),
                assignee_id=_person_id(_text(row.owner), db),
                collaborator_ids=[person_id for person_id in (_person_id(name, db) for name in _split_names(row.collaborators)) if person_id is not None],
                plan_time=_text(row.plan_time) or _combine_plan_time(row.plan_start, row.plan_end),
                status=_text(row.status) or "未开始",
                completion_criteria="",
                notes=_subtask_notes(row),
            )
            db.add(subtask)
            db.flush()
            subtasks_created += 1
            crud.log(db, current_user, "批量导入建关键任务", "subtask", subtask.id, {}, {"title": key_task_name})

            issue_text = _text(row.issue)
            if issue_text:
                db.add(
                    models.Issue(
                        project_id=project.id,
                        special_project=project_name,
                        related_task_id=task.id,
                        description=issue_text,
                        owner=_text(row.owner),
                        source_type=ST.normalize("批量导入"),
                        status="待处理",
                        priority="中",
                    )
                )
                issues_created += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "projects_created": projects_created,
        "projects_matched": projects_matched,
        "tasks_created": tasks_created,
        "subtasks_created": subtasks_created,
        "issues_created": issues_created,
        "duplicates_skipped": duplicates_skipped,
        "skipped_rows": 0,
    }
