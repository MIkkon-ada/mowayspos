"""Review-only AI work-plan import helpers.

This module deliberately stops at a normalized draft/row projection. Database
mutation remains in ``project_plan_import.import_project_plan_rows`` and is
only called after the user confirms the preview.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from .. import models, schemas
from ..ai.contracts import AIInvocationContext, AIServiceError
from ..ai.service import AIService
from .project_init_ai_agent import (
    ProjectInitAiResult,
    generate_project_init_draft,
    generate_structured_project_init_draft,
)
from .project_init_file_parser import parse_project_init_file


@dataclass(frozen=True)
class ProjectPlanAiImportDraft:
    result: ProjectInitAiResult
    fallback_mode: str = "ai"
    source_files: tuple[str, ...] = ()


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".txt", ".docx", ".doc", ".pdf"}


def _fallback_mode_for_result(result: ProjectInitAiResult) -> str:
    if result.provider == "local-rule" or result.model_name in {
        "structured-spreadsheet",
        "semantic-source-repair",
    }:
        return "deterministic"
    return "ai"


def _existing_task_context(db: Session, project_id: int | None) -> list[dict[str, object]]:
    if project_id is None:
        return []
    tasks = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id, models.Task.is_deleted.is_(False))
        .order_by(models.Task.id.asc())
        .all()
    )
    result: list[dict[str, object]] = []
    for task in tasks:
        subtasks = (
            db.query(models.SubTask)
            .filter(models.SubTask.task_id == task.id, models.SubTask.is_deleted.is_(False))
            .order_by(models.SubTask.id.asc())
            .all()
        )
        result.append(
            {
                "id": task.id,
                "title": task.key_task,
                "subtasks": [{"id": item.id, "title": item.title} for item in subtasks],
            }
        )
    return result


def _person_context(db: Session) -> list[dict[str, object]]:
    return [
        {
            "id": person.id,
            "name": person.name,
            "is_active": bool(person.is_active),
            "is_project_member": True,
        }
        for person in db.query(models.Person)
        .filter(models.Person.is_active.is_(True))
        .order_by(models.Person.id.asc())
        .all()
    ]


def analyze_project_plan_upload(
    db: Session,
    content: bytes,
    original_name: str,
    *,
    actor: str,
    project_name: str = "",
    target_project_id: int | None = None,
) -> ProjectPlanAiImportDraft:
    """Parse and analyze an upload without creating business records."""

    file_name = Path(original_name or "").name
    extension = Path(file_name).suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的工作计划文件格式：{extension or '未知'}")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("工作计划文件大小不能超过 25 MiB")
    if target_project_id is not None:
        project = db.get(models.Project, target_project_id)
        if project is None:
            raise ValueError("目标项目不存在")
        target_name = str(project.name or "").strip()
    else:
        target_name = ""

    with TemporaryDirectory(prefix="project-plan-ai-") as raw_directory:
        path = Path(raw_directory) / file_name
        path.write_bytes(content)
        chunks = parse_project_init_file(path, file_name)
        people = _person_context(db)
        existing_tasks = _existing_task_context(db, target_project_id)
        context = AIInvocationContext(
            actor=actor,
            resource_type="project_plan_import",
            resource_id=target_project_id,
        )
        try:
            result = generate_project_init_draft(
                chunks,
                people,
                existing_tasks,
                ai_service=AIService(db),
                invocation_context=context,
            )
            fallback_mode = _fallback_mode_for_result(result)
        except AIServiceError:
            result = generate_structured_project_init_draft(
                chunks,
                people,
                existing_tasks,
            )
            if result is None:
                raise
            fallback_mode = "deterministic"

    if target_name or str(project_name or "").strip():
        profile = result.project_profile.model_copy(
            update={"name": target_name or str(project_name).strip()}
        )
        result = result.model_copy(update={"project_profile": profile})
    source_files = tuple(dict.fromkeys(chunk.file_name for chunk in chunks))
    return ProjectPlanAiImportDraft(
        result=result,
        fallback_mode=fallback_mode,
        source_files=source_files,
    )


def _combine_plan_time(start: str, end: str) -> str:
    start = str(start or "").strip()
    end = str(end or "").strip()
    if start and end:
        return f"{start}~{end}"
    return start or end


def _evidence_notes(task, subtask) -> str:
    values: list[str] = []
    process = str(task.process or "").strip()
    if process:
        values.append(f"推进流程：{process}")
    seen: set[str] = set()
    for evidence in [*task.evidence, *subtask.evidence]:
        label = f"{evidence.file_name} · {evidence.location}"
        if label not in seen:
            seen.add(label)
            values.append(f"来源：{label}")
    return "\n".join(values)


def draft_to_batch_rows(
    draft: ProjectInitAiResult | ProjectPlanAiImportDraft,
    *,
    project_name_override: str = "",
) -> list[schemas.BatchImportRow]:
    """Convert a review-only AI draft into the existing import contract."""

    result = draft.result if isinstance(draft, ProjectPlanAiImportDraft) else draft
    project_name = str(project_name_override or result.project_profile.name or "").strip()
    if not project_name:
        raise ValueError("项目名称不能为空")

    rows: list[schemas.BatchImportRow] = []
    for task in result.tasks:
        workstream = str(task.title or "").strip()
        if not workstream:
            raise ValueError("重点工作不能为空")
        if not task.subtasks:
            raise ValueError(f"重点工作“{workstream}”缺少关键任务")
        for subtask in task.subtasks:
            key_task = str(subtask.title or "").strip()
            if not key_task:
                raise ValueError(f"重点工作“{workstream}”存在空关键任务")
            owner = str(subtask.assignee_name or task.owner_name or "").strip()
            collaborators = "、".join(
                name.strip() for name in subtask.helper_names if str(name or "").strip()
            )
            plan_start = str(subtask.plan_start or task.plan_start or "").strip()
            plan_end = str(subtask.plan_end or task.plan_end or "").strip()
            status = str(subtask.status or task.status or "未开始").strip()
            rows.append(
                schemas.BatchImportRow(
                    project_name=project_name,
                    project_objective=str(result.project_profile.objectives or "").strip(),
                    workstream=workstream,
                    key_task=key_task,
                    key_achievement=str(task.goal or "").strip(),
                    completion_standard=str(task.acceptance_criteria or "").strip(),
                    owner=owner,
                    collaborators=collaborators,
                    plan_time=_combine_plan_time(plan_start, plan_end),
                    plan_start=plan_start,
                    plan_end=plan_end,
                    workstream_plan_start=str(task.plan_start or "").strip(),
                    workstream_plan_end=str(task.plan_end or "").strip(),
                    status=status,
                    notes=_evidence_notes(task, subtask),
                )
            )
    if not rows:
        raise ValueError("AI 未识别到可导入的关键任务")
    return rows
