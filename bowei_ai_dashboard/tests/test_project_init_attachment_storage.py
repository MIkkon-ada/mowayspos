from pathlib import Path

import pytest

from app.services.project_init_attachment_storage import (
    BACKEND_ROOT,
    project_init_attachment_path,
    project_init_attachment_root,
)


def test_attachment_root_defaults_to_persistent_project_data(monkeypatch):
    monkeypatch.delenv("PROJECT_INIT_ATTACHMENT_ROOT", raising=False)

    assert project_init_attachment_root() == (
        BACKEND_ROOT / "data" / "project-init-attachments"
    ).resolve()


def test_attachment_root_honors_explicit_configuration(monkeypatch, tmp_path):
    configured_root = tmp_path / "attachments"
    monkeypatch.setenv("PROJECT_INIT_ATTACHMENT_ROOT", str(configured_root))

    assert project_init_attachment_root() == configured_root.resolve()


def test_attachment_path_rejects_paths_outside_storage_root(tmp_path):
    root = tmp_path / "attachments"

    with pytest.raises(ValueError, match="outside"):
        project_init_attachment_path("../other.xlsx", root=root)


def test_attachment_path_stays_under_storage_root(tmp_path):
    root = tmp_path / "attachments"

    assert project_init_attachment_path("7/source.xlsx", root=root) == (
        root / "7" / "source.xlsx"
    ).resolve()
