import hashlib
import os
from pathlib import Path
import unicodedata
import uuid


MAX_TASK_PLAN_ATTACHMENT_COUNT = 10
MAX_TASK_PLAN_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_TASK_PLAN_SUFFIXES = {".docx", ".xlsx", ".txt"}


_MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}


class TaskPlanProposalAttachmentError(ValueError):
    pass


def _root_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).resolve()


def _safe_path(root: Path, storage_key: str) -> Path:
    if not isinstance(storage_key, str) or not storage_key.strip() or "\x00" in storage_key:
        raise TaskPlanProposalAttachmentError("Attachment storage key is invalid")

    path = (root / storage_key).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise TaskPlanProposalAttachmentError("Attachment storage key is outside storage root") from exc
    return path


def _validate_project_id(project_id: int) -> None:
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
        raise TaskPlanProposalAttachmentError("Project ID must be a positive integer")


def _validate_filename(filename: str) -> tuple[str, str]:
    if not isinstance(filename, str) or not filename:
        raise TaskPlanProposalAttachmentError("Attachment filename is invalid")
    if len(filename) > 255:
        raise TaskPlanProposalAttachmentError("Attachment filename is too long")
    if any(unicodedata.category(character) == "Cc" for character in filename):
        raise TaskPlanProposalAttachmentError("Attachment filename contains a control character")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise TaskPlanProposalAttachmentError("Attachment filename must be a basename")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_TASK_PLAN_SUFFIXES:
        raise TaskPlanProposalAttachmentError("Attachment file type is not supported")
    return filename, suffix


def _validate_attachment(
    project_id: int, filename: str, content: bytes
) -> tuple[str, str]:
    _validate_project_id(project_id)
    original_name, suffix = _validate_filename(filename)
    if not isinstance(content, bytes) or not content:
        raise TaskPlanProposalAttachmentError("Attachment content cannot be empty")
    if len(content) > MAX_TASK_PLAN_ATTACHMENT_BYTES:
        raise TaskPlanProposalAttachmentError("Attachment exceeds the maximum size")
    return original_name, suffix


def _attachment_destination(root: Path, project_id: int, suffix: str) -> tuple[str, Path]:
    storage_key = f"{project_id}/{uuid.uuid4().hex}{suffix}"
    return storage_key, _safe_path(root, storage_key)


def _attachment_result(
    original_name: str,
    storage_key: str,
    suffix: str,
    content: bytes,
    path: Path,
) -> dict:
    return {
        "original_name": original_name,
        "storage_key": storage_key,
        "mime_type": _MIME_TYPES[suffix],
        "size_bytes": len(content),
        "content_hash": hashlib.sha256(content).hexdigest(),
        "path": path,
    }


def save_task_plan_attachment(
    root: str | os.PathLike[str], *, project_id: int, filename: str, content: bytes
) -> dict:
    return save_task_plan_attachments(
        root, project_id=project_id, attachments=[(filename, content)]
    )[0]


def save_task_plan_attachments(
    root: str | os.PathLike[str],
    *,
    project_id: int,
    attachments: list[tuple[str, bytes]],
    existing_attachment_count: int = 0,
) -> list[dict]:
    """Save one request batch after the router has counted its persisted run attachments."""
    _validate_project_id(project_id)
    if (
        isinstance(existing_attachment_count, bool)
        or not isinstance(existing_attachment_count, int)
        or existing_attachment_count < 0
    ):
        raise TaskPlanProposalAttachmentError("Existing attachment count must be a non-negative integer")

    attachment_batch = list(attachments)
    if existing_attachment_count + len(attachment_batch) > MAX_TASK_PLAN_ATTACHMENT_COUNT:
        raise TaskPlanProposalAttachmentError("Attachment maximum count exceeded")

    validated_attachments = [
        (*_validate_attachment(project_id, filename, content), content)
        for filename, content in attachment_batch
    ]
    root_path = _root_path(root)
    saved_attachments = []
    written_storage_keys = []
    try:
        for original_name, suffix, content in validated_attachments:
            storage_key, path = _attachment_destination(root_path, project_id, suffix)
            written_storage_keys.append(storage_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            saved_attachments.append(
                _attachment_result(
                    original_name, storage_key, suffix, content, path
                )
            )
    except Exception:
        for storage_key in reversed(written_storage_keys):
            remove_task_plan_attachment(root_path, storage_key)
        raise

    return saved_attachments


def remove_task_plan_attachment(root: str | os.PathLike[str], storage_key: str) -> None:
    path = _safe_path(_root_path(root), storage_key)
    if path.is_file():
        path.unlink()
