from pathlib import Path

import pytest

from app.services.project_purge_storage import (
    ProjectPurgeStorageError,
    destroy_staged_project_payloads,
    restore_staged_project_payloads,
    stage_project_payloads,
)


def test_stage_then_destroy_removes_only_project_payloads(tmp_path: Path):
    root = tmp_path / "achievement"
    payload = root / "7" / "asset.bin"
    other = root / "8" / "keep.bin"
    payload.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    payload.write_bytes(b"delete")
    other.write_bytes(b"keep")

    staged = stage_project_payloads(
        "00000000-0000-0000-0000-000000000007",
        [("achievement", root, "7/asset.bin")],
    )

    assert not payload.exists()
    assert other.read_bytes() == b"keep"
    destroy_staged_project_payloads(staged)
    assert not (root / ".project-purge").exists()
    assert other.read_bytes() == b"keep"


def test_failed_stage_restores_previously_moved_payload(tmp_path: Path):
    root = tmp_path / "init"
    payload = root / "7" / "init.pdf"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"source")

    with pytest.raises(ProjectPurgeStorageError):
        stage_project_payloads(
            "00000000-0000-0000-0000-000000000008",
            [("init", root, "7/init.pdf"), ("init", root, "../outside")],
        )

    assert payload.read_bytes() == b"source"
    assert not (root / ".project-purge").exists()


def test_restore_is_idempotent_and_rejects_escape_paths(tmp_path: Path):
    root = tmp_path / "meeting"

    with pytest.raises(ProjectPurgeStorageError):
        stage_project_payloads(
            "00000000-0000-0000-0000-000000000009",
            [("meeting", root, "../../outside")],
        )

    restore_staged_project_payloads([])


def test_stage_rejects_a_storage_key_that_resolves_to_a_directory(tmp_path: Path):
    root = tmp_path / "achievement"
    nested_file = root / "7" / "must-not-move.bin"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_bytes(b"keep")

    with pytest.raises(ProjectPurgeStorageError):
        stage_project_payloads(
            "00000000-0000-0000-0000-000000000010",
            [("achievement", root, "7")],
        )

    assert nested_file.read_bytes() == b"keep"
    assert not (root / ".project-purge").exists()
