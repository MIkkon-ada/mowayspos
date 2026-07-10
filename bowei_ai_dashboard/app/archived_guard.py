"""归档项目只读守卫。

业务语义：当项目 status == "archived" 或 lifecycle_status == "archived" 时，
禁止继续向该项目写入业务数据（重点工作 / 关键任务 / 汇报 / 确认 / 成果 / 问题 / 会议）。

设计原则：
- 只拦截写接口，读取接口不受影响（归档项目仍可查看/导出）。
- 不修改数据库结构，不新增表，不新增字段。
- project_id 为 None 时跳过守卫（由调用方自行决定是否允许无项目写入）。
- 项目不存在时跳过守卫（由其它 404 校验处理）。
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models

_ARCHIVED = "archived"


def _is_archived(value: str | None) -> bool:
    return bool(value) and value.strip().lower() == _ARCHIVED


def require_project_not_archived(project_id: int | None, db: Session) -> None:
    """如果项目已归档，抛出 403「项目已归档，不允许继续写入。」

    Args:
        project_id: 项目 ID；为 None 时直接放行（调用方需自行保证语义正确）。
        db: SQLAlchemy Session。

    Raises:
        HTTPException(403): 项目 status 或 lifecycle_status 为 archived。
    """
    if project_id is None:
        return
    proj = db.get(models.Project, project_id)
    if proj is None:
        return
    if _is_archived(getattr(proj, "status", "")):
        raise HTTPException(403, "项目已归档，不允许继续写入。")
    if _is_archived(getattr(proj, "lifecycle_status", "")):
        raise HTTPException(403, "项目已归档，不允许继续写入。")
