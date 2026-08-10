from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile
from starlette.formparsers import FormData, MultiPartException, MultiPartParser, parse_options_header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import crud, models
from ..database import get_db
from .. import schemas
from ..permissions import (
    get_current_user_name,
    get_user_context_from_db,
    require_project_access,
    require_project_manager,
    require_project_owner_or_admin,
)
from ..time_utils import utc_now
from ..services.project_init_analysis import (
    build_project_init_snapshot,
    process_analysis_run,
    recover_stale_run,
    recover_stale_runs,
    validate_analysis_attachment_selection,
)


router = APIRouter(prefix="/api/projects/{project_id}/init-attachments", tags=["project-init-ai"])
analysis_router = APIRouter(prefix="/api/projects/{project_id}/init-analysis-runs", tags=["project-init-ai"])
logger = logging.getLogger(__name__)

_ROOT = Path(os.getenv("PROJECT_INIT_ATTACHMENT_ROOT", "/app/data/project-init-attachments"))
_MAX_FILE_BYTES = 25 * 1024 * 1024
_MAX_MULTIPART_OVERHEAD = 128 * 1024
_EDITABLE_LIFECYCLES = {"dispatched", "returned"}
_CHUNK_BYTES = 1024 * 1024
_MAX_FORM_FIELDS = 4
_MAX_FORM_FIELD_BYTES = 64 * 1024
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}
_OOXML_REQUIRED_MEMBERS = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
}


def _serialize(row: models.ProjectInitAttachment) -> dict:
    return crud.to_dict(row)


def _get_project(project_id: int, db: Session) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _require_editable_project(project_id: int, db: Session) -> models.Project:
    project = _get_project(project_id, db)
    if str(project.status or "").strip().lower() not in _EDITABLE_LIFECYCLES:
        raise HTTPException(status_code=409, detail="project lifecycle is not editable")
    return project


def _authorize_access(project_id: int, current_user: str, db: Session) -> models.Project:
    project = _get_project(project_id, db)
    require_project_access(current_user, project_id, db)
    return project


def _authorize_edit(project_id: int, current_user: str, db: Session) -> models.Project:
    project = _require_editable_project(project_id, db)
    require_project_owner_or_admin(current_user, project_id, db)
    return project


def _lock_editable_project(project_id: int, current_user: str, db: Session) -> models.Project:
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id)
        .with_for_update()
        .one_or_none()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if str(project.status or "").strip().lower() not in _EDITABLE_LIFECYCLES:
        raise HTTPException(status_code=409, detail="project lifecycle is not editable")

    # SQLite parses FOR UPDATE but does not acquire a row lock.  A real,
    # rollback-safe timestamp write upgrades the transaction to a writer
    # before the attachment row is changed, preventing a lifecycle update
    # from committing between the final status check and that write.
    if db.get_bind().dialect.name.lower() == "sqlite":
        project.updated_at = utc_now()
        db.flush()
        db.refresh(project)
        if str(project.status or "").strip().lower() not in _EDITABLE_LIFECYCLES:
            raise HTTPException(status_code=409, detail="project lifecycle is not editable")
    require_project_owner_or_admin(current_user, project_id, db)
    return project


class _AttachmentRequestTooLarge(MultiPartException):
    pass


class _LimitedMultiPartParser(MultiPartParser):
    def __init__(self, *args, max_file_size: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_file_size = max_file_size
        self._current_file_size = 0

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_size = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self._current_file_size += end - start
            if self._current_file_size > self.max_file_size:
                raise _AttachmentRequestTooLarge("attachment exceeds maximum size")
        super().on_part_data(data, start, end)


def _check_request_size(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        request_bytes = int(content_length)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid content length") from exc
    if request_bytes < 0:
        raise HTTPException(status_code=400, detail="invalid content length")
    if request_bytes > _MAX_FILE_BYTES + _MAX_MULTIPART_OVERHEAD:
        raise HTTPException(status_code=413, detail="request exceeds 25 MiB file limit")


async def _bounded_request_stream(request: Request):
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > _MAX_FILE_BYTES + _MAX_MULTIPART_OVERHEAD:
            raise _AttachmentRequestTooLarge("request exceeds maximum size")
        yield chunk


async def _parse_upload_from_request(request: Request) -> UploadFile:
    _check_request_size(request)
    content_type = request.headers.get("content-type", "")
    media_type, _ = parse_options_header(content_type.encode("latin-1"))
    if media_type != b"multipart/form-data":
        raise HTTPException(status_code=400, detail="multipart form data is required")
    parser = _LimitedMultiPartParser(
        request.headers,
        _bounded_request_stream(request),
        max_files=1,
        max_fields=_MAX_FORM_FIELDS,
        max_part_size=_MAX_FORM_FIELD_BYTES,
        max_file_size=_MAX_FILE_BYTES,
    )
    try:
        form: FormData = await parser.parse()
    except _AttachmentRequestTooLarge as exc:
        raise HTTPException(status_code=413, detail="file exceeds 25 MiB limit") from exc
    except MultiPartException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=422, detail="file is required")
    await file.seek(0)
    return file


def _root_path() -> Path:
    return _ROOT.resolve()


def _attachment_path(row: models.ProjectInitAttachment) -> Path:
    root = _root_path()
    path = (root / row.storage_key).resolve()
    if path == root or root not in path.parents:
        raise HTTPException(status_code=404, detail="attachment not found")
    return path


def _retry_deleted_payload_cleanup(db: Session) -> None:
    rows = (
        db.query(models.ProjectInitAttachment)
        .filter(models.ProjectInitAttachment.deleted_at.is_not(None))
        .limit(100)
        .all()
    )
    for row in rows:
        try:
            _attachment_path(row).unlink(missing_ok=True)
        except (HTTPException, OSError):
            logger.warning(
                "project init attachment cleanup retry failed for attachment_id=%s",
                row.id,
                exc_info=True,
            )


def _validate_payload(path: Path, original_name: str, extension: str) -> None:
    try:
        with path.open("rb") as source:
            header = source.read(8)
        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="file signature does not match extension")
        if extension in {".doc", ".xls"} and header != _OLE_SIGNATURE:
            raise HTTPException(status_code=422, detail="file signature does not match extension")
        if extension in _OOXML_REQUIRED_MEMBERS:
            if not zipfile.is_zipfile(path):
                raise HTTPException(status_code=422, detail="file signature does not match extension")
            with zipfile.ZipFile(path) as archive:
                if _OOXML_REQUIRED_MEMBERS[extension] not in archive.namelist():
                    raise HTTPException(status_code=422, detail="file structure does not match extension")
        if extension == ".txt":
            with path.open("rb") as source:
                while chunk := source.read(_CHUNK_BYTES):
                    if b"\x00" in chunk:
                        raise HTTPException(status_code=422, detail="text file contains binary data")
    except HTTPException:
        raise
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid file: {original_name}") from exc


def _safe_original_name(raw_name: str | None) -> str:
    name = Path(raw_name or "").name
    name = "".join("_" if ord(char) < 32 or ord(char) == 127 else char for char in name)
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=422, detail="filename is required")
    if len(name) > 255:
        raise HTTPException(status_code=422, detail="filename is too long")
    return name


def _safe_extension(original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    if extension not in _MIME_BY_EXTENSION:
        raise HTTPException(status_code=422, detail="file type not allowed")
    return extension


def _analysis_run_response(run: models.ProjectInitAnalysisRun) -> dict:
    attachment_ids = _json_list(run.attachment_ids_json)
    draft = _json_value(run.current_draft_json, {})
    metadata = _json_value(run.result_json, {})
    if not isinstance(metadata, dict):
        metadata = {}
    file_results = _json_value(run.file_results_json, [])
    if isinstance(file_results, list):
        metadata = {**metadata, "file_results": file_results}
    return {
        "id": run.id,
        "project_id": run.project_id,
        "attachment_ids": attachment_ids,
        "status": run.status,
        "stage": run.stage,
        "progress": run.progress,
        "error_message": run.error_summary or "",
        "draft": draft,
        "result_metadata": metadata,
        "created_at": run.created_at,
        "started_at": getattr(run, "started_at", None),
        "finished_at": getattr(run, "finished_at", None),
        "applied_at": getattr(run, "applied_at", None),
    }


def _json_value(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _json_list(value: str | None) -> list[int]:
    parsed = _json_value(value, [])
    return parsed if isinstance(parsed, list) else []


def _get_analysis_run(project_id: int, run_id: int, db: Session) -> models.ProjectInitAnalysisRun:
    run = db.get(models.ProjectInitAnalysisRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return run


def _create_analysis_run(
    project_id: int,
    attachment_ids: list[int],
    current_draft,
    current_user: str,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    _authorize_edit(project_id, current_user, db)
    project = _lock_editable_project(project_id, current_user, db)
    current_draft_json = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        for item in (current_draft or [])
    ]
    rows = (
        db.query(models.ProjectInitAttachment)
        .filter(models.ProjectInitAttachment.id.in_(attachment_ids))
        .all()
    )
    selected = validate_analysis_attachment_selection(attachment_ids, rows, project)
    snapshot = build_project_init_snapshot(db, project, selected, current_draft_json)
    context = get_user_context_from_db(current_user, db)
    run = models.ProjectInitAnalysisRun(
        project_id=project_id,
        attachment_ids_json=json.dumps(attachment_ids, ensure_ascii=False),
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        current_draft_json=json.dumps(current_draft_json, ensure_ascii=False),
        status="queued",
        stage="reading",
        progress=0,
        result_json="{}",
        file_results_json="[]",
        error_summary="",
        created_by=current_user,
        created_by_person_id=context.get("person_id"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(process_analysis_run, run.id)
    return _analysis_run_response(run)


def _create_retry_from_frozen_snapshot(
    project_id: int,
    old_run: models.ProjectInitAnalysisRun,
    current_user: str,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    """Create one retry from the old run's immutable snapshot only.

    The unique retry link makes the insert itself the cross-session
    de-duplication point.  No live attachment rows are consulted here.
    """
    _authorize_edit(project_id, current_user, db)
    snapshot = _json_value(old_run.snapshot_json, {})
    if not isinstance(snapshot, dict) or not snapshot.get("attachments"):
        raise HTTPException(status_code=409, detail="analysis run has no frozen attachment snapshot")
    attachment_ids = _json_list(old_run.attachment_ids_json)
    current_draft = snapshot.get("current_draft", [])
    context = get_user_context_from_db(current_user, db)
    run = models.ProjectInitAnalysisRun(
        project_id=project_id,
        attachment_ids_json=json.dumps(attachment_ids, ensure_ascii=False),
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        current_draft_json=json.dumps(current_draft, ensure_ascii=False),
        status="queued",
        stage="reading",
        progress=0,
        result_json="{}",
        file_results_json="[]",
        error_summary="",
        created_by=current_user,
        created_by_person_id=context.get("person_id"),
        retry_of_run_id=old_run.id,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(models.ProjectInitAnalysisRun)
            .filter(
                models.ProjectInitAnalysisRun.project_id == project_id,
                models.ProjectInitAnalysisRun.retry_of_run_id == old_run.id,
            )
            .order_by(models.ProjectInitAnalysisRun.id.asc())
            .first()
        )
        if existing is None:
            raise HTTPException(status_code=409, detail="analysis retry is already being created")
        return _analysis_run_response(existing)
    db.refresh(run)
    background_tasks.add_task(process_analysis_run, run.id)
    return _analysis_run_response(run)


@router.post("", status_code=201)
async def upload_init_attachment(
    project_id: int,
    request: Request,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _check_request_size(request)
    _retry_deleted_payload_cleanup(db)
    _authorize_edit(project_id, current_user, db)
    file = await _parse_upload_from_request(request)
    root = _root_path()
    temp_path = root / f".upload-{uuid.uuid4().hex}"
    destination: Path | None = None
    size_bytes = 0
    committed = False
    try:
        original_name = _safe_original_name(file.filename)
        extension = _safe_extension(original_name)
        root.mkdir(parents=True, exist_ok=True)
        with temp_path.open("wb") as output:
            while chunk := await file.read(_CHUNK_BYTES):
                size_bytes += len(chunk)
                if size_bytes > _MAX_FILE_BYTES:
                    raise HTTPException(status_code=413, detail="file exceeds 25 MiB limit")
                output.write(chunk)
        _validate_payload(temp_path, original_name, extension)

        storage_key = f"{project_id}/{uuid.uuid4().hex}"
        destination = (root / storage_key).resolve()
        if root not in destination.parents:
            raise HTTPException(status_code=500, detail="invalid attachment storage path")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(destination))
        _lock_editable_project(project_id, current_user, db)
        user_context = get_user_context_from_db(current_user, db)
        row = models.ProjectInitAttachment(
            project_id=project_id,
            storage_key=storage_key,
            original_name=original_name,
            mime_type=_MIME_BY_EXTENSION[extension],
            size_bytes=size_bytes,
            uploaded_by=current_user,
            uploaded_by_person_id=user_context.get("person_id"),
        )
        db.add(row)
        db.flush()
        crud.log(
            db,
            current_user,
            "project_init_attachment_upload",
            "project_init_attachment",
            row.id,
            {},
            _serialize(row),
            project_id=project_id,
        )
        db.commit()
        committed = True
        return _serialize(row)
    except Exception:
        if not committed:
            temp_path.unlink(missing_ok=True)
            if destination is not None:
                destination.unlink(missing_ok=True)
            db.rollback()
        else:
            logger.error(
                "project init attachment response failed after commit; retaining payload for recovery attachment_id=%s",
                getattr(row, "id", None),
                exc_info=True,
            )
        raise
    finally:
        await file.close()


@router.get("")
def list_init_attachments(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _retry_deleted_payload_cleanup(db)
    _authorize_access(project_id, current_user, db)
    rows = (
        db.query(models.ProjectInitAttachment)
        .filter(
            models.ProjectInitAttachment.project_id == project_id,
            models.ProjectInitAttachment.deleted_at.is_(None),
        )
        .order_by(models.ProjectInitAttachment.created_at.desc())
        .all()
    )
    return [_serialize(row) for row in rows]


@router.get("/{attachment_id}/download")
def download_init_attachment(
    project_id: int,
    attachment_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _retry_deleted_payload_cleanup(db)
    _get_project(project_id, db)
    require_project_manager(current_user, project_id, db)
    row = db.get(models.ProjectInitAttachment, attachment_id)
    if row is None or row.deleted_at is not None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="attachment not found")
    path = _attachment_path(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="attachment not found")
    extension = _safe_extension(row.original_name)
    return FileResponse(
        path,
        media_type=_MIME_BY_EXTENSION[extension],
        filename=row.original_name,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{attachment_id}")
def delete_init_attachment(
    project_id: int,
    attachment_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _retry_deleted_payload_cleanup(db)
    _authorize_edit(project_id, current_user, db)
    _lock_editable_project(project_id, current_user, db)
    row = (
        db.query(models.ProjectInitAttachment)
        .filter(
            models.ProjectInitAttachment.id == attachment_id,
            models.ProjectInitAttachment.project_id == project_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail="attachment not found")
    before = _serialize(row)
    deleted_at = utc_now()
    row.deleted_at = deleted_at
    row.deleted_by = current_user
    db.flush()
    crud.log(
        db,
        current_user,
        "project_init_attachment_delete",
        "project_init_attachment",
        row.id,
        before,
        _serialize(row),
        project_id=project_id,
    )
    db.commit()
    try:
        _attachment_path(row).unlink(missing_ok=True)
    except (HTTPException, OSError):
        logger.warning("project init attachment cleanup failed for attachment_id=%s", row.id, exc_info=True)
    return {"ok": True}


@analysis_router.post("", response_model=schemas.ProjectInitAnalysisRunResponse, status_code=201)
def create_project_init_analysis_run(
    project_id: int,
    payload: schemas.ProjectInitAnalysisCreate,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _authorize_edit(project_id, current_user, db)
    recover_stale_runs(db, project_id)
    return _create_analysis_run(
        project_id,
        payload.attachment_ids,
        getattr(payload, "current_draft", []),
        current_user,
        db,
        background_tasks,
    )


@analysis_router.get("/latest", response_model=schemas.ProjectInitAnalysisRunResponse)
def latest_project_init_analysis_run(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _authorize_access(project_id, current_user, db)
    recover_stale_runs(db, project_id)
    run = (
        db.query(models.ProjectInitAnalysisRun)
        .filter(models.ProjectInitAnalysisRun.project_id == project_id)
        .order_by(models.ProjectInitAnalysisRun.created_at.desc(), models.ProjectInitAnalysisRun.id.desc())
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return _analysis_run_response(run)


@analysis_router.get("/{run_id}", response_model=schemas.ProjectInitAnalysisRunResponse)
def get_project_init_analysis_run(
    project_id: int,
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _authorize_access(project_id, current_user, db)
    recover_stale_runs(db, project_id)
    return _analysis_run_response(_get_analysis_run(project_id, run_id, db))


@analysis_router.post("/{run_id}/retry", response_model=schemas.ProjectInitAnalysisRunResponse, status_code=201)
def retry_project_init_analysis_run(
    project_id: int,
    run_id: int,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _authorize_edit(project_id, current_user, db)
    old_run = _get_analysis_run(project_id, run_id, db)
    stale = recover_stale_run(old_run, db=db)
    if old_run.status not in {"failed", "partial_failed"}:
        raise HTTPException(status_code=409, detail="analysis run is not retryable")
    return _create_retry_from_frozen_snapshot(project_id, old_run, current_user, db, background_tasks)


@analysis_router.post("/{run_id}/apply", response_model=schemas.ProjectInitAnalysisRunResponse)
def apply_project_init_analysis_run(
    project_id: int,
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _authorize_edit(project_id, current_user, db)
    run = _get_analysis_run(project_id, run_id, db)
    if run.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=409, detail=f"analysis run status {run.status} cannot be applied")
    if run.applied_at is None:
        applied_at = utc_now()
        result = (
            db.query(models.ProjectInitAnalysisRun)
            .filter(
                models.ProjectInitAnalysisRun.id == run_id,
                models.ProjectInitAnalysisRun.project_id == project_id,
                models.ProjectInitAnalysisRun.status.in_(["completed", "partial_failed"]),
                models.ProjectInitAnalysisRun.applied_at.is_(None),
            )
            .update({models.ProjectInitAnalysisRun.applied_at: applied_at}, synchronize_session=False)
        )
        db.commit()
        if result != 1:
            run = _get_analysis_run(project_id, run_id, db)
        else:
            run.applied_at = applied_at
    return _analysis_run_response(run)
