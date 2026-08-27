"""Persistent, review-only project-init analysis runs.

The worker deliberately treats a run as a leased state machine.  Every
mutation after the initial claim is conditional on ``status == processing``;
this prevents stale-run recovery from being undone by an old worker.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import case, or_, update
from sqlalchemy.orm import Session, object_session

from .. import crud, models
from ..database import SessionLocal
from ..time_utils import utc_now
from .project_init_ai_agent import ProjectInitAiInvalidDraft, generate_project_init_draft
from ..ai.service import AIService
from ..ai.contracts import AIInvocationContext
from .project_init_file_parser import parse_project_init_file

logger = logging.getLogger(__name__)

MAX_ANALYSIS_ATTACHMENTS = 10
MAX_ANALYSIS_BYTES = 100 * 1024 * 1024
STALE_AFTER = timedelta(minutes=30)
_ROOT = Path(os.getenv("PROJECT_INIT_ATTACHMENT_ROOT", "/app/data/project-init-attachments"))


class RunLeaseLost(RuntimeError):
    """The worker no longer owns the processing lease."""


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
    policy = (
        db.query(models.AICapabilityPolicy)
        .filter_by(capability_key="project.init.analysis", enabled=True)
        .one_or_none()
    )
    model_ids = [] if policy is None or policy.primary_model_id is None else [
        policy.primary_model_id,
        *(_json_load(policy.fallback_model_ids_json, [])),
    ]
    model_rows = {item.id: item for item in db.query(models.AIModel).filter(models.AIModel.id.in_(model_ids)).all()} if model_ids else {}
    model_strategy = [
        {
            "id": model.id,
            "code": model.code,
            "display_name": model.display_name,
            "provider": model.provider,
            "model_name": model.model_name,
        }
        for model_id in model_ids
        if (model := model_rows.get(model_id)) is not None
    ]
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
        "model_strategy": model_strategy,
    }


def _attachment_path(storage_key: str) -> Path:
    root = _ROOT.resolve()
    path = (root / storage_key).resolve()
    if path == root or root not in path.parents:
        raise ValueError("invalid attachment storage path")
    return path


def _safe_error(kind: str) -> str:
    return {
        "parse": "attachment parsing failed; please check the source and retry",
        "ai": "AI analysis failed; please retry later",
        "empty": "no usable tasks were extracted",
        "stale": "analysis run became stale; please retry",
        "generic": "analysis failed; please retry",
    }.get(kind, "analysis failed; please retry")


def _progress_value(progress: int):
    bounded = min(100, max(0, int(progress)))
    return case(
        (models.ProjectInitAnalysisRun.progress < bounded, bounded),
        else_=models.ProjectInitAnalysisRun.progress,
    )


def _update_processing(
    db: Session,
    run_id: int,
    *,
    stage: str | None = None,
    progress: int | None = None,
    values: dict[str, Any] | None = None,
) -> bool:
    """Update a leased run only while it is still processing."""
    update_values: dict[str, Any] = {"updated_at": utc_now()}
    if stage is not None:
        update_values["stage"] = stage
    if progress is not None:
        update_values["progress"] = _progress_value(progress)
    if values:
        update_values.update(values)
    result = db.execute(
        update(models.ProjectInitAnalysisRun)
        .where(
            models.ProjectInitAnalysisRun.id == run_id,
            models.ProjectInitAnalysisRun.status == "processing",
        )
        .values(**update_values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def _set_progress(db: Session, run: models.ProjectInitAnalysisRun, *, stage: str, progress: int) -> bool:
    changed = _update_processing(db, run.id, stage=stage, progress=progress)
    if changed:
        db.refresh(run)
    return changed


def _claim_run(db: Session, run_id: int) -> bool:
    now = utc_now()
    result = db.execute(
        update(models.ProjectInitAnalysisRun)
        .where(
            models.ProjectInitAnalysisRun.id == run_id,
            models.ProjectInitAnalysisRun.status == "queued",
        )
        .values(
            status="processing",
            stage="parsing",
            progress=_progress_value(5),
            started_at=now,
            updated_at=now,
            error_summary="",
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def recover_stale_run(run: models.ProjectInitAnalysisRun, *, now=None, db: Session | None = None) -> bool:
    session = db or object_session(run)
    if session is None:
        return False
    current = now or utc_now()
    heartbeat = run.updated_at or run.started_at
    if run.status != "processing" or heartbeat is None or current - heartbeat <= STALE_AFTER:
        return False
    result = session.execute(
        update(models.ProjectInitAnalysisRun)
        .where(
            models.ProjectInitAnalysisRun.id == run.id,
            models.ProjectInitAnalysisRun.status == "processing",
            or_(
                models.ProjectInitAnalysisRun.updated_at <= heartbeat,
                models.ProjectInitAnalysisRun.updated_at.is_(None),
            ),
        )
        .values(
            status="failed",
            stage="stale",
            progress=_progress_value(100),
            finished_at=current,
            updated_at=current,
            error_summary=_safe_error("stale"),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        return False
    session.commit()
    return True


def recover_stale_runs(db: Session, project_id: int) -> int:
    cutoff = utc_now() - STALE_AFTER
    now = utc_now()
    result = db.execute(
        update(models.ProjectInitAnalysisRun)
        .where(
            models.ProjectInitAnalysisRun.project_id == project_id,
            models.ProjectInitAnalysisRun.status == "processing",
            or_(
                models.ProjectInitAnalysisRun.updated_at < cutoff,
                (
                    models.ProjectInitAnalysisRun.updated_at.is_(None)
                    & (models.ProjectInitAnalysisRun.started_at < cutoff)
                ),
            ),
        )
        .values(
            status="failed",
            stage="stale",
            progress=_progress_value(100),
            finished_at=now,
            updated_at=now,
            error_summary=_safe_error("stale"),
        )
        .execution_options(synchronize_session=False)
    )
    changed = int(result.rowcount or 0)
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


def _attempted_models(db: Session, run_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(models.AIInvocationLog, models.AIModel)
        .join(models.AIModel, models.AIInvocationLog.model_id == models.AIModel.id)
        .filter(
            models.AIInvocationLog.resource_type == "project_init",
            models.AIInvocationLog.resource_id == run_id,
        )
        .order_by(models.AIInvocationLog.id.asc())
        .all()
    )
    return [
        {"id": model.id, "code": model.code, "display_name": model.display_name, "provider": model.provider, "model_name": model.model_name}
        for _, model in rows
    ]


def _result_metadata(draft: dict[str, Any], *, provider: str = "", model_name: str = "", file_results=None, attempted_models=None) -> dict[str, Any]:
    tasks = draft.get("tasks") if isinstance(draft.get("tasks"), list) else []
    warnings = draft.get("warnings") if isinstance(draft.get("warnings"), list) else []
    return {
        "provider": provider,
        "model_name": model_name,
        "task_count": len(tasks),
        "warning_count": len(warnings),
        "file_count": len(file_results or []),
        "attempted_models": attempted_models or [],
        "final_model": attempted_models[-1] if attempted_models else {},
    }


def _mark_failed(db: Session, run_id: int, kind: str) -> bool:
    return _update_processing(
        db,
        run_id,
        stage="failed",
        progress=100,
        values={
            "status": "failed",
            "finished_at": utc_now(),
            "error_summary": _safe_error(kind),
        },
    )


def process_analysis_run(run_id: int) -> None:
    """Process one run using a fresh connection and an atomic lease claim."""
    db = SessionLocal()
    try:
        if not _claim_run(db, run_id):
            return
        run = db.get(models.ProjectInitAnalysisRun, run_id)
        if run is None:
            return
        snapshot = _json_load(run.snapshot_json, {})
        attachment_snapshot = snapshot.get("attachments", []) if isinstance(snapshot, dict) else []
        # Compatibility for pre-snapshot rows only; new and retried runs always
        # carry complete frozen metadata and never query live attachments.
        if not attachment_snapshot:
            attachment_snapshot = []
            for attachment_id in _json_load(run.attachment_ids_json, []):
                attachment_snapshot.append({"id": attachment_id, "storage_key": "", "original_name": ""})

        file_results: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        for index, item in enumerate(attachment_snapshot):
            attachment_id = item.get("id")
            try:
                path = _attachment_path(str(item["storage_key"]))
                parsed = list(parse_project_init_file(path, str(item["original_name"])))
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
            except Exception as exc:
                logger.warning(
                    "project_init_parse_failure run_id=%s error_type=%s code=parse_failure",
                    run_id,
                    type(exc).__name__,
                )
                file_results.append({"attachment_id": attachment_id, "status": "failed", "error": _safe_error("parse")})
            if not _update_processing(
                db,
                run_id,
                stage="parsing",
                progress=10 + int(35 * (index + 1) / max(1, len(attachment_snapshot))),
                values={"file_results_json": _json_dump(file_results)},
            ):
                return

        if not chunks:
            _mark_failed(db, run_id, "parse")
            return
        if not _update_processing(db, run_id, stage="extracting", progress=55):
            return

        people = snapshot.get("people", []) if isinstance(snapshot, dict) else []
        existing_tasks = snapshot.get("tasks", []) if isinstance(snapshot, dict) else []
        try:
            result = generate_project_init_draft(
                chunks,
                people,
                existing_tasks,
                ai_service=AIService(db),
                invocation_context=AIInvocationContext(resource_type="project_init", resource_id=run_id),
            )
            draft = _draft_payload(result)
        except Exception as exc:
            failure_category = (
                "invalid_draft_schema"
                if isinstance(exc, ProjectInitAiInvalidDraft)
                else "ai_processing_failed"
            )
            logger.warning(
                "project_init_provider_failure run_id=%s error_type=%s code=provider_failure",
                run_id,
                type(exc).__name__,
            )
            _update_processing(
                db,
                run_id,
                stage="failed",
                progress=100,
                values={
                    "current_draft_json": _json_dump({"tasks": [], "warnings": []}),
                    "result_json": _json_dump(
                        {
                            "tasks": 0,
                            "warnings": 0,
                            "attempted_models": _attempted_models(db, run_id),
                            "failure_category": failure_category,
                        }
                    ),
                    "file_results_json": _json_dump(file_results),
                    "status": "failed",
                    "finished_at": utc_now(),
                    "error_summary": _safe_error("ai"),
                },
            )
            return

        if not _set_progress(db, run, stage="matching", progress=75):
            return
        if not _set_progress(db, run, stage="merging", progress=90):
            return
        provider = str(getattr(result, "provider", "") or "")[:30]
        model_name = str(getattr(result, "model_name", "") or "")[:100]
        failed_files = sum(1 for item in file_results if item.get("status") == "failed")
        _update_processing(
            db,
            run_id,
            stage="completed",
            progress=100,
            values={
                "current_draft_json": _json_dump(draft),
                "provider": provider,
                "model_name": model_name,
                "result_json": _json_dump(
                    _result_metadata(draft, provider=provider, model_name=model_name, file_results=file_results, attempted_models=_attempted_models(db, run_id))
                ),
                "file_results_json": _json_dump(file_results),
                "status": "partial_failed" if failed_files else "completed",
                "finished_at": utc_now(),
                "error_summary": _safe_error("parse") if failed_files else "",
            },
        )
    except RunLeaseLost:
        logger.warning("project_init_worker_stopped run_id=%s code=lease_lost", run_id)
    except Exception as exc:
        logger.error(
            "project_init_worker_failure run_id=%s error_type=%s code=worker_failure",
            run_id,
            type(exc).__name__,
        )
        try:
            db.rollback()
            _mark_failed(db, run_id, "generic")
        except Exception as persist_exc:
            logger.error(
                "project_init_failure_persist_failed run_id=%s error_type=%s code=persist_failure",
                run_id,
                type(persist_exc).__name__,
            )
    finally:
        db.close()
