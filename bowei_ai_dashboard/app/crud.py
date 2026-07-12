import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .services.project_resolution import resolve_project_context


def validate_subtask_link(
    db: Session,
    project_id: int | None,
    related_task_id: int | None,
    related_subtask_id: int | None,
) -> None:
    """校验 project_id / related_task_id / related_subtask_id 一致性，防止跨项目错配。

    规则：
    1. related_subtask_id 为空 → 直接通过。
    2. related_subtask_id 不为空但 related_task_id 为空 → 422。
    3. SubTask 必须存在且未被删除。
    4. SubTask.task_id 必须等于 related_task_id。
    5. Task 必须存在且未被删除。
    6. Task.project_id 必须等于 project_id（project_id 为 None 时跳过）。
    """
    if related_subtask_id is None:
        return

    if related_task_id is None:
        raise HTTPException(422, "关联关键任务时必须同时关联重点工作。")

    subtask = db.get(models.SubTask, related_subtask_id)
    if not subtask or bool(getattr(subtask, "is_deleted", False)):
        raise HTTPException(422, "关键任务不存在或已删除。")

    if subtask.task_id != related_task_id:
        raise HTTPException(422, "关键任务不属于所选重点工作。")

    task = db.get(models.Task, related_task_id)
    if not task or bool(getattr(task, "is_deleted", False)):
        raise HTTPException(422, "重点工作不存在或已删除。")

    if project_id is not None and task.project_id != project_id:
        raise HTTPException(422, "重点工作不属于当前项目。")


def to_dict(obj):
    data = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        if isinstance(value, datetime):
            value = value.isoformat(timespec="seconds") + "Z"
        data[col.name] = value
    return data


def log(
    db: Session,
    operator: str,
    action: str,
    target_type: str,
    target_id: int | None,
    before: Any = None,
    after: Any = None,
    *,
    project_id: int | None = None,
    note: str = "",
):
    db.add(
        models.OperationLog(
            project_id=project_id,
            operator=operator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            note=note,
            before_json=json.dumps(before or {}, ensure_ascii=False),
            after_json=json.dumps(after or {}, ensure_ascii=False),
        )
    )


def update_model(obj, data: dict):
    for key, value in data.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
    return obj


def get_project_name_by_id(project_id: int, db: Session) -> str | None:
    """按 project_id 查项目名称，用于展示兼容。"""
    return resolve_project_context(db, project_id=project_id)["project_name"]
