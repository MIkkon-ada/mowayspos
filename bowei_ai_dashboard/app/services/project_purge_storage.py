from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from uuid import UUID


class ProjectPurgeStorageError(RuntimeError):
    """A project purge attempted to access an unsafe or unavailable payload."""


@dataclass(frozen=True)
class StagedProjectPayload:
    cleanup_key: str
    root: Path
    source: Path
    staged: Path


def _normalize_cleanup_key(cleanup_key: str) -> str:
    try:
        return str(UUID(cleanup_key))
    except (TypeError, ValueError) as exc:
        raise ProjectPurgeStorageError("invalid project purge cleanup key") from exc


def _quarantine_root(root: Path, cleanup_key: str) -> Path:
    resolved_root = root.resolve()
    base = (resolved_root / ".project-purge").resolve()
    target = (base / cleanup_key).resolve()
    if target == base or base not in target.parents:
        raise ProjectPurgeStorageError("invalid project purge quarantine path")
    return target


def _safe_payload_path(root: Path, storage_key: str) -> Path:
    if not isinstance(storage_key, str) or not storage_key.strip() or "\x00" in storage_key:
        raise ProjectPurgeStorageError("invalid project attachment storage key")
    resolved_root = root.resolve()
    path = (resolved_root / storage_key).resolve()
    quarantine_base = (resolved_root / ".project-purge").resolve()
    if path == resolved_root or resolved_root not in path.parents or path == quarantine_base or quarantine_base in path.parents:
        raise ProjectPurgeStorageError("invalid project attachment storage path")
    return path


def _remove_empty_quarantine_base(root: Path) -> None:
    base = (root.resolve() / ".project-purge").resolve()
    try:
        if base.exists() and not any(base.iterdir()):
            base.rmdir()
    except OSError as exc:
        raise ProjectPurgeStorageError("project attachment cleanup pending") from exc


def stage_project_payloads(
    cleanup_key: str,
    entries: list[tuple[str, Path, str]],
) -> list[StagedProjectPayload]:
    """Move project payloads into a same-root quarantine before DB deletion."""
    normalized_key = _normalize_cleanup_key(cleanup_key)
    staged: list[StagedProjectPayload] = []
    try:
        for _kind, root, storage_key in entries:
            resolved_root = root.resolve()
            source = _safe_payload_path(resolved_root, storage_key)
            if not source.exists():
                continue
            if not source.is_file():
                raise ProjectPurgeStorageError("project attachment payload is not a regular file")
            quarantine = _quarantine_root(resolved_root, normalized_key)
            target = (quarantine / source.relative_to(resolved_root)).resolve()
            if target == quarantine or quarantine not in target.parents:
                raise ProjectPurgeStorageError("invalid project purge quarantine path")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            staged.append(
                StagedProjectPayload(
                    cleanup_key=normalized_key,
                    root=resolved_root,
                    source=source,
                    staged=target,
                )
            )
        return staged
    except Exception as exc:
        try:
            restore_staged_project_payloads(staged)
        except ProjectPurgeStorageError:
            pass
        if isinstance(exc, ProjectPurgeStorageError):
            raise
        raise ProjectPurgeStorageError("project attachment staging failed") from exc


def restore_staged_project_payloads(staged: list[StagedProjectPayload]) -> None:
    """Restore moved payloads after a database transaction does not commit."""
    roots_by_key: set[tuple[Path, str]] = set()
    try:
        for item in reversed(staged):
            roots_by_key.add((item.root, item.cleanup_key))
            if not item.staged.exists():
                continue
            if item.source.exists():
                raise ProjectPurgeStorageError("project attachment restore target already exists")
            item.source.parent.mkdir(parents=True, exist_ok=True)
            item.staged.replace(item.source)
        for root, cleanup_key in roots_by_key:
            quarantine = _quarantine_root(root, cleanup_key)
            if quarantine.exists():
                rmtree(quarantine)
            _remove_empty_quarantine_base(root)
    except OSError as exc:
        raise ProjectPurgeStorageError("project attachment restore failed") from exc


def retry_project_payload_cleanup(cleanup_key: str, roots: list[Path]) -> bool:
    """Idempotently remove only the named quarantine directory below each root."""
    normalized_key = _normalize_cleanup_key(cleanup_key)
    try:
        for root in {entry.resolve() for entry in roots}:
            quarantine = _quarantine_root(root, normalized_key)
            if quarantine.exists():
                rmtree(quarantine)
            _remove_empty_quarantine_base(root)
    except OSError as exc:
        raise ProjectPurgeStorageError("project attachment cleanup pending") from exc
    return True


def destroy_staged_project_payloads(staged: list[StagedProjectPayload]) -> None:
    """Physically delete a successfully committed project's staged files."""
    if not staged:
        return
    retry_project_payload_cleanup(staged[0].cleanup_key, [item.root for item in staged])
