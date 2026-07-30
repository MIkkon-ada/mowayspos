from __future__ import annotations

import os
import shutil
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import crud, models
from ..database import get_db
from ..permissions import (
    PROJECT_ROLE_OWNER,
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    is_project_member,
    require_project_access,
)
from ..time_utils import utc_now
from ..services.project_close import require_project_business_writable

router = APIRouter(prefix="/api/achievement-attachments", tags=["achievement-attachments"])
logger = logging.getLogger(__name__)

_ROOT = Path(os.getenv("ACHIEVEMENT_ATTACHMENT_ROOT", "/app/data/achievement-attachments"))
_MAX_FILE_BYTES = 20 * 1024 * 1024
_MAX_TOTAL_BYTES = 100 * 1024 * 1024
_MULTIPART_OVERHEAD_BYTES = 64 * 1024
_MIME_BY_EXTENSION = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    "zip": "application/zip", "rar": "application/vnd.rar",
}
_ALLOWED_EXTENSIONS = set(_MIME_BY_EXTENSION)
_DANGEROUS_DECLARED_MIME_TYPES = {
    "text/html", "application/xhtml+xml", "image/svg+xml", "application/javascript", "text/javascript",
}


def _serialize(row: models.AchievementAttachment) -> dict:
    return crud.to_dict(row)


def _require_upload_permission(current_user: str, project_id: int, db: Session) -> dict:
    context = get_user_context_from_db(current_user, db)
    if context.get("is_tech_admin"):
        return context
    person_id = context.get("person_id")
    if person_id is None or not is_project_member(person_id, project_id, db):
        raise HTTPException(403, "permission denied")
    return context


def _require_delete_permission(current_user: str, row: models.AchievementAttachment, db: Session) -> None:
    context = get_user_context_from_db(current_user, db)
    if context.get("is_tech_admin") or row.uploaded_by == current_user:
        return
    person_id = context.get("person_id")
    if person_id is not None and PROJECT_ROLE_OWNER in get_all_project_roles(person_id, row.project_id, db):
        return
    raise HTTPException(403, "permission denied")


def _attachment_path(row: models.AchievementAttachment) -> Path:
    # storage_key is generated server-side, but keep download path rooted defensively.
    path = (_ROOT / row.storage_key).resolve()
    root = _ROOT.resolve()
    if root not in path.parents:
        raise HTTPException(404, "attachment not found")
    return path


def _canonical_mime_type(original_name: str) -> str | None:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    return _MIME_BY_EXTENSION.get(extension)


def _retry_deleted_payload_cleanup(db: Session) -> None:
    """Use durable soft-delete metadata as a cleanup queue on later requests."""
    rows = db.query(models.AchievementAttachment).filter(
        models.AchievementAttachment.deleted_at.is_not(None),
    ).limit(100).all()
    for row in rows:
        try:
            _attachment_path(row).unlink(missing_ok=True)
        except OSError:
            logger.warning("attachment payload cleanup retry failed for attachment_id=%s", row.id, exc_info=True)


@router.post("", status_code=201)
def upload_attachment(
    request: Request,
    project_id: int = Form(...),
    file: UploadFile = File(...),
    achievement_id: int | None = Form(None),
    achievement_submission_id: int | None = Form(None),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _retry_deleted_payload_cleanup(db)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_FILE_BYTES + _MULTIPART_OVERHEAD_BYTES:
                raise HTTPException(413, "request exceeds 20 MiB file limit")
        except ValueError:
            raise HTTPException(422, "invalid content length")
    if achievement_id is not None and achievement_submission_id is not None:
        raise HTTPException(422, "only one achievement target is allowed")
    context = _require_upload_permission(current_user, project_id, db)
    # Lock the project for the whole quota check/metadata transaction. PostgreSQL
    # serializes concurrent uploads for a project, preventing quota oversubscription.
    project = db.query(models.Project).filter(models.Project.id == project_id).with_for_update().first()
    if not project:
        raise HTTPException(404, "project not found")
    require_project_business_writable(project_id, db)
    if achievement_id is not None:
        achievement = db.get(models.Achievement, achievement_id)
        if not achievement or achievement.project_id != project_id:
            raise HTTPException(422, "achievement does not belong to project")
    if achievement_submission_id is not None:
        submission = db.get(models.AchievementSubmission, achievement_submission_id)
        if not submission or submission.project_id != project_id:
            raise HTTPException(422, "achievement submission does not belong to project")
        from .achievement_submissions import _STATUS_PENDING

        if submission.status != _STATUS_PENDING:
            raise HTTPException(422, "achievement submission is not pending")
        if submission.submitter != current_user:
            person_id = context.get("person_id")
            is_owner = person_id is not None and any(
                role in {"owner", PROJECT_ROLE_OWNER}
                for role in get_all_project_roles(person_id, project_id, db)
            )
            if not context.get("is_tech_admin") and not is_owner:
                raise HTTPException(403, "permission denied")

    original_name = Path(file.filename or "").name
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(422, "file type not allowed")
    if (file.content_type or "").lower() in _DANGEROUS_DECLARED_MIME_TYPES:
        raise HTTPException(422, "unsafe declared file type")
    canonical_mime_type = _MIME_BY_EXTENSION[extension]

    _ROOT.mkdir(parents=True, exist_ok=True)
    temp_path = _ROOT / f".upload-{uuid.uuid4().hex}"
    destination: Path | None = None
    size_bytes = 0
    try:
        with temp_path.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > _MAX_FILE_BYTES:
                    raise HTTPException(422, "file exceeds 20 MiB limit")
                out.write(chunk)
        total = db.query(func.coalesce(func.sum(models.AchievementAttachment.size_bytes), 0)).filter(
            models.AchievementAttachment.project_id == project_id,
            models.AchievementAttachment.deleted_at.is_(None),
        ).scalar()
        if int(total or 0) + size_bytes > _MAX_TOTAL_BYTES:
            raise HTTPException(422, "achievement attachments exceed 100 MiB limit")

        storage_key = f"{project_id}/{uuid.uuid4().hex}"
        destination = _ROOT / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(destination))
        context = get_user_context_from_db(current_user, db)
        row = models.AchievementAttachment(
            project_id=project_id, achievement_id=achievement_id,
            achievement_submission_id=achievement_submission_id, storage_key=storage_key,
            original_name=original_name, mime_type=canonical_mime_type,
            size_bytes=size_bytes, uploaded_by=current_user,
            uploaded_by_person_id=context.get("person_id"),
        )
        db.add(row)
        db.flush()
        crud.log(db, current_user, "achievement_attachment_upload", "achievement_attachment", row.id, {}, _serialize(row), project_id=project_id)
        db.commit(); db.refresh(row)
        return _serialize(row)
    except Exception:
        temp_path.unlink(missing_ok=True)
        if destination is not None:
            destination.unlink(missing_ok=True)
        db.rollback()
        raise
    finally:
        file.file.close()


@router.get("")
def list_attachments(
    achievement_id: int | None = None,
    achievement_submission_id: int | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _retry_deleted_payload_cleanup(db)
    if achievement_id is None and achievement_submission_id is None:
        raise HTTPException(422, "achievement_id or achievement_submission_id is required")
    project_ids: set[int] = set()
    if achievement_id is not None:
        achievement = db.get(models.Achievement, achievement_id)
        if not achievement or achievement.project_id is None:
            raise HTTPException(404, "achievement not found")
        project_ids.add(int(achievement.project_id))
    if achievement_submission_id is not None:
        submission = db.get(models.AchievementSubmission, achievement_submission_id)
        if not submission or submission.project_id is None:
            raise HTTPException(404, "achievement submission not found")
        project_ids.add(int(submission.project_id))
    for project_id in project_ids:
        require_project_access(current_user, project_id, db)
    query = db.query(models.AchievementAttachment).filter(models.AchievementAttachment.deleted_at.is_(None))
    if achievement_id is not None:
        query = query.filter(models.AchievementAttachment.achievement_id == achievement_id)
    if achievement_submission_id is not None:
        query = query.filter(models.AchievementAttachment.achievement_submission_id == achievement_submission_id)
    rows = query.order_by(models.AchievementAttachment.created_at.desc()).all()
    return [_serialize(row) for row in rows]


@router.get("/{attachment_id}/download")
def download_attachment(attachment_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _retry_deleted_payload_cleanup(db)
    row = db.get(models.AchievementAttachment, attachment_id)
    if not row or row.deleted_at is not None:
        raise HTTPException(404, "attachment not found")
    require_project_access(current_user, row.project_id, db)
    path = _attachment_path(row)
    if not path.is_file():
        raise HTTPException(404, "attachment not found")
    mime_type = _canonical_mime_type(row.original_name)
    if mime_type is None:
        raise HTTPException(404, "attachment not found")
    return FileResponse(
        path, media_type=mime_type, filename=row.original_name,
        content_disposition_type="attachment", headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{attachment_id}")
def delete_attachment(attachment_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _retry_deleted_payload_cleanup(db)
    row = db.get(models.AchievementAttachment, attachment_id)
    if not row or row.deleted_at is not None:
        raise HTTPException(404, "attachment not found")
    require_project_business_writable(row.project_id, db)
    _require_delete_permission(current_user, row, db)
    before = _serialize(row)
    row.deleted_at = utc_now()
    row.deleted_by = current_user
    crud.log(db, current_user, "achievement_attachment_delete", "achievement_attachment", row.id, before, _serialize(row), project_id=row.project_id)
    db.commit()
    # Retain audit metadata only; the deleted payload is no longer downloadable.
    try:
        _attachment_path(row).unlink(missing_ok=True)
    except OSError:
        logger.warning("attachment payload cleanup failed for attachment_id=%s", row.id, exc_info=True)
    return {"ok": True}
