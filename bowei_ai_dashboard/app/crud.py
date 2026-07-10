import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from . import models
from .services.project_resolution import resolve_project_context


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
