"""Safe, project-scoped storage helpers for original meeting Word files."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any


MAX_MEETING_DOCUMENT_BYTES = 20 * 1024 * 1024
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class MeetingDocumentStorageError(ValueError):
    """Raised when an uploaded or stored meeting document is unsafe."""


def _root_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).resolve()


def _safe_path(root: Path, storage_key: str) -> Path:
    if not isinstance(storage_key, str) or not storage_key.strip() or "\x00" in storage_key:
        raise MeetingDocumentStorageError("invalid meeting document storage key")
    path = (root / storage_key).resolve()
    if path == root or root not in path.parents:
        raise MeetingDocumentStorageError("invalid meeting document storage path")
    return path


def validate_docx_upload(filename: str, content: bytes) -> str:
    """Validate one upload and return its safe original basename."""
    if not isinstance(filename, str) or not filename.strip() or Path(filename).name != filename:
        raise MeetingDocumentStorageError("invalid meeting document filename")
    if Path(filename).suffix.lower() != ".docx":
        raise MeetingDocumentStorageError("meeting minutes must be a .docx file")
    if not isinstance(content, bytes) or not content:
        raise MeetingDocumentStorageError("meeting document cannot be empty")
    if len(content) > MAX_MEETING_DOCUMENT_BYTES:
        raise MeetingDocumentStorageError("meeting document exceeds 20 MiB")
    return filename.strip()


def save_meeting_document(
    root: str | os.PathLike[str], project_id: int, filename: str, content: bytes
) -> dict[str, Any]:
    """Save original bytes under a server-generated project-scoped key."""
    original_name = validate_docx_upload(filename, content)
    if not isinstance(project_id, int) or project_id <= 0:
        raise MeetingDocumentStorageError("project_id must be a positive integer")
    root_path = _root_path(root)
    storage_key = f"{project_id}/{uuid.uuid4().hex}.docx"
    path = _safe_path(root_path, storage_key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    except OSError as exc:
        raise MeetingDocumentStorageError("meeting document could not be saved") from exc
    return {
        "storage_key": storage_key,
        "path": path,
        "original_name": original_name,
        "mime_type": DOCX_MIME_TYPE,
        "size_bytes": len(content),
        "content_hash": hashlib.sha256(content).hexdigest(),
    }


def download_meeting_document_path(root: str | os.PathLike[str], storage_key: str) -> Path:
    """Return an existing stored path without exposing arbitrary filesystem paths."""
    path = _safe_path(_root_path(root), storage_key)
    if not path.is_file():
        raise MeetingDocumentStorageError("meeting document not found")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise MeetingDocumentStorageError("meeting document not found") from exc
    if size > MAX_MEETING_DOCUMENT_BYTES:
        raise MeetingDocumentStorageError("stored meeting document exceeds 20 MiB")
    return path


def read_meeting_document(root: str | os.PathLike[str], storage_key: str) -> bytes:
    """Read a stored original document through the same safe path check."""
    path = download_meeting_document_path(root, storage_key)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise MeetingDocumentStorageError("meeting document could not be read") from exc
