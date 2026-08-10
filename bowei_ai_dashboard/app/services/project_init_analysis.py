"""Persistent, review-only project-init analysis runs."""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models
from ..database import SessionLocal
from ..time_utils import utc_now
from .project_init_ai_agent import generate_project_init_draft
from .project_init_file_parser import parse_project_init_file

logger = logging.getLogger(__name__)

MAX_ANALYSIS_ATTACHMENTS = 10
MAX_ANALYSIS_BYTES = 100 * 1024 * 1024
STALE_AFTER = timedelta(minutes=30)
_ROOT = Path(os.getenv("PROJECT_INIT_ATTACHMENT_ROOT", "/app/data/project-init-attachments"))


def _json_load(value: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def validate_analysis_attachment_selection(
    attachment_ids: Iterable[int],
    attachments: Iterable[models.ProjectInitAttachment | Any],
    project: models.Project | dict[str, Any],
) -> list[models.ProjectInitAttachment | Any]:
    """Validate the frozen attachment set before a run is created."""
    ids = list(attachment_ids)
    if not 1 <= len(ids) <= MAX_ANALYSIS_ATTACHMENTS or len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="analysis requires 1 to 10 unique attachments")
    project_id = project.get("project_id") if isinstance(project, dict) else project.id
    rows = list(attachments)
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(ids) or any(row_id not in by_id for row_id in ids):
        raise HTTPException(status_code=404, detail="attachment not found")
    selected = [by_id[row_id] for row_id in ids]
    if any(row.project_id != project_id or row.deleted_at is not None for row in selected):
        raise HTTPException(status_code=404, detail="attachment not found")
    total_size = sum(max(0, int(row.size_bytes or 0)) for row in selected)
    if total_size > MAX_ANALYSIS_BYTES:
        raise HTTPException(status_code=413, detail="analysis attachments exceed 100 MiB")
    return selected


def _snapshot_task(db: Session, task: models.Task) -> dict[str, Any]:
    data = crud.to_dict(task)
    subtasks = (
        db.query(models.SubTask)
        .filter(models.SubTask.task_id == task.id, models.SubTask.is_deleted.is_(False))
        .order_by(models.SubTask.id.asc())
        .all()
    )
    data["subtasks"] = [crud.to_dict(item) for item in subtasks]
    return data


def build_project_init_snapshot(
    db: Session,
    project: models.Project,
    attachments: Iterable[models.ProjectInitAttachment],
    current_draft: Any = None,
) -> dict[str, Any]:
    member_rows = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project.id)
        .order_by(models.ProjectMember.id.asc())
        .all()
    )
    member_ids = {row.person_id for row in member_rows}
    people = (
        db.query(models.Person)
        .filter(models.Person.id.in_(member_ids))
        .order_by(models.Person.id.asc())
        .all()
        if member_ids
        else []
    )
    tasks = (
        db.query(models.Task)
        .filter(models.Task.project_id == project.id, models.Task.is_deleted.is_(False))
        .order_by(models.Task.id.asc())
        .all()
    )
    return {
        "project": crud.to_dict(project),
        "members": [crud.to_dict(item) for item in member_rows],
        "people": [crud.to_dict(item) for item in people],
        "tasks": [_snapshot_task(db, item) for item in tasks],
        "attachments": [
            {
                "id": item.id,
                "storage_key": item.storage_key,
                "original_name": item.original_name,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
            }
            for item in attachments
        ],
        "current_draft": current_draft if current_draft is not None else [],
    }


def _attachment_path(storage_key: str) -> Path:
    root = _ROOT.resolve()
    path = (root / storage_key).resolve()
    if path == root or root not in path.parents:
        raise ValueError("invalid attachment storage path")
    return path


def _safe_error(kind: str) -> str:
    messages = {
        "parse": "附件解析失败，请检查文件内容后重试",
        "ai": "AI 分析失败，请稍后重试",
        "empty": "未提取到可用任务，请检查附件内容",
        "stale": "analysis run stale; please retry",
        "generic": "分析任务失败，请重试",
    }
    return messages.get(kind, messages["generic"])


def _set_progress(db: Session, run: models.ProjectInitAnalysisRun, *, stage: str, progress: int) -> None:
    run.stage = stage
    run.progress = max(int(run.progress or 0), min(100, progress))
    db.commit()


def recover_stale_run(run: models.ProjectInitAnalysisRun, *, now=None) -> bool:
    if run.status != "processing":
        return False
    started_at = run.started_at or run.updated_at
    if started_at is None or (now or utc_now()) - started_at <= STALE_AFTER:
        return False
    run.status = "failed"
    run.stage = "stale"
    run.finished_at = now or utc_now()
    run.error_summary = _safe_error("stale")
    return True


def recover_stale_runs(db: Session, project_id: int) -> int:
    rows = (
        db.query(models.ProjectInitAnalysisRun)
        .filter(
            models.ProjectInitAnalysisRun.project_id == project_id,
            models.ProjectInitAnalysisRun.status == "processing",
        )
        .all()
    )
    changed = sum(1 for row in rows if recover_stale_run(row))
    if changed:
        db.commit()
    return changed


def _draft_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        try:
            value = result.model_dump(mode="json")
        except TypeError:
            value = result.model_dump()
    elif isinstance(result, dict):
        value = result
    else:
        value = {"tasks": []}
    return value if isinstance(value, dict) else {"tasks": []}


def _result_metadata(draft: dict[str, Any], *, provider: str = "", model_name: str = "", file_results=None) -> dict[str, Any]:
    tasks = draft.get("tasks") if isinstance(draft.get("tasks"), list) else []
    warnings = draft.get("warnings") if isinstance(draft.get("warnings"), list) else []
    return {
        "provider": provider,
        "model_name": model_name,
        "task_count": len(tasks),
        "warning_count": len(warnings),
        "file_count": len(file_results or []),
    }


def process_analysis_run(run_id: int) -> None:
    """Process one run using a fresh SessionLocal connection."""
    db = SessionLocal()
    try:
        run = db.get(models.ProjectInitAnalysisRun, run_id)
        if run is None or run.status != "queued":
            return
        now = utc_now()
        run.status = "processing"
        run.stage = "parsing"
        run.progress = max(run.progress or 0, 5)
        run.started_at = now
        run.error_summary = ""
        db.commit()

        snapshot = _json_load(run.snapshot_json, {})
        attachment_snapshot = snapshot.get("attachments", []) if isinstance(snapshot, dict) else []
        if not attachment_snapshot:
            # Runs created before the runtime snapshot migration can still be
            # completed safely; new runs always use the immutable snapshot.
            attachment_ids = _json_load(run.attachment_ids_json, [])
            legacy_rows = (
                db.query(models.ProjectInitAttachment)
                .filter(models.ProjectInitAttachment.id.in_(attachment_ids))
                .all()
                if attachment_ids
                else []
            )
            attachment_snapshot = [
                {
                    "id": item.id,
                    "storage_key": item.storage_key,
                    "original_name": item.original_name,
                    "mime_type": item.mime_type,
                    "size_bytes": item.size_bytes,
                }
                for item in legacy_rows
            ]
        file_results: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        for index, item in enumerate(attachment_snapshot):
            attachment_id = item.get("id")
            try:
                path = _attachment_path(str(item["storage_key"]))
                parsed = parse_project_init_file(path, str(item["original_name"]))
                for chunk in parsed:
                    file_name = chunk.get("file_name", "") if isinstance(chunk, dict) else chunk.file_name
                    location = chunk.get("location", "") if isinstance(chunk, dict) else chunk.location
                    text = chunk.get("text", "") if isinstance(chunk, dict) else chunk.text
                    chunks.append(
                        {
                            "attachment_id": attachment_id,
                            "file_name": file_name,
                            "location": location,
                            "text": text,
                        }
                    )
                file_results.append({"attachment_id": attachment_id, "status": "completed", "chunk_count": len(parsed)})
            except Exception:
                logger.exception("project init analysis parse failed run_id=%s attachment_id=%s", run_id, attachment_id)
                file_results.append({"attachment_id": attachment_id, "status": "failed", "error": _safe_error("parse")})
            _set_progress(db, run, stage="parsing", progress=10 + int(35 * (index + 1) / max(1, len(attachment_snapshot))))

        run.file_results_json = _json_dump(file_results)
        db.commit()
        if not chunks:
            run.status = "failed"
            run.stage = "failed"
            run.progress = 100
            run.finished_at = utc_now()
            run.error_summary = _safe_error("parse")
            db.commit()
            return

        _set_progress(db, run, stage="extracting", progress=max(run.progress, 55))
        people = snapshot.get("people", []) if isinstance(snapshot, dict) else []
        existing_tasks = snapshot.get("tasks", []) if isinstance(snapshot, dict) else []
        try:
            result = generate_project_init_draft(chunks, people, existing_tasks)
            draft = _draft_payload(result)
        except Exception:
            logger.exception("project init analysis AI failed run_id=%s", run_id)
            draft = {"tasks": [], "warnings": [{"code": "analysis_failed", "message": _safe_error("ai")}]}
            run.current_draft_json = _json_dump(draft)
            run.result_json = _json_dump(_result_metadata(draft, file_results=file_results))
            run.file_results_json = _json_dump(file_results)
            run.status = "failed"
            run.stage = "failed"
            run.progress = 100
            run.finished_at = utc_now()
            run.error_summary = _safe_error("ai")
            db.commit()
            return

        _set_progress(db, run, stage="matching", progress=max(run.progress, 75))
        _set_progress(db, run, stage="merging", progress=max(run.progress, 90))
        run.current_draft_json = _json_dump(draft)
        run.provider = str(getattr(result, "provider", "") or "")[:30]
        run.model_name = str(getattr(result, "model_name", "") or "")[:100]
        run.result_json = _json_dump(
            _result_metadata(
                draft,
                provider=run.provider,
                model_name=run.model_name,
                file_results=file_results,
            )
        )
        run.file_results_json = _json_dump(file_results)
        failed_files = sum(1 for item in file_results if item.get("status") == "failed")
        run.status = "partial_failed" if failed_files else "completed"
        run.stage = "completed"
        run.progress = 100
        run.finished_at = utc_now()
        run.error_summary = "部分附件处理失败，请检查来源后重试" if failed_files else ""
        db.commit()
    except Exception:
        logger.exception("project init analysis worker failed run_id=%s", run_id)
        try:
            db.rollback()
            run = db.get(models.ProjectInitAnalysisRun, run_id)
            if run is not None:
                run.status = "failed"
                run.stage = "failed"
                run.progress = max(int(run.progress or 0), 100)
                run.finished_at = utc_now()
                run.error_summary = _safe_error("generic")
                db.commit()
        except Exception:
            logger.exception("project init analysis failure state could not be persisted run_id=%s", run_id)
    finally:
        db.close()
