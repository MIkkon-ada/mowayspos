"""Safe, durable storage locations for project-init source attachments."""

from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ATTACHMENT_ROOT = BACKEND_ROOT / "data" / "project-init-attachments"


def project_init_attachment_root() -> Path:
    """Return the configured attachment root, or a durable local default."""

    configured_root = os.getenv("PROJECT_INIT_ATTACHMENT_ROOT", "").strip()
    root = Path(configured_root).expanduser() if configured_root else _DEFAULT_ATTACHMENT_ROOT
    return root.resolve()


def project_init_attachment_path(storage_key: str, *, root: Path | None = None) -> Path:
    """Resolve an attachment key while preventing traversal outside its root."""

    attachment_root = (root or project_init_attachment_root()).resolve()
    attachment_path = (attachment_root / storage_key).resolve()
    if attachment_path == attachment_root or attachment_root not in attachment_path.parents:
        raise ValueError("Attachment path is outside the configured storage root")
    return attachment_path
