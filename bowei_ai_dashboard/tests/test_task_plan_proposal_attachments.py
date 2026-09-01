import hashlib
from pathlib import Path

import pytest

from app.services.task_plan_proposal_attachments import (
    TaskPlanProposalAttachmentError,
    remove_task_plan_attachment,
    save_task_plan_attachment,
)


def test_save_task_plan_attachment_isolates_projects_and_preserves_content(tmp_path):
    root = tmp_path / "attachments"

    first = save_task_plan_attachment(
        root, project_id=17, filename="plan.txt", content=b"project 17 plan"
    )
    second = save_task_plan_attachment(
        root, project_id=18, filename="plan.txt", content=b"project 18 plan"
    )

    assert first["storage_key"].startswith("17/")
    assert second["storage_key"].startswith("18/")
    assert first["storage_key"] != second["storage_key"]
    assert first["path"] == (root / first["storage_key"]).resolve()
    assert second["path"] == (root / second["storage_key"]).resolve()
    assert first["path"].read_bytes() == b"project 17 plan"
    assert second["path"].read_bytes() == b"project 18 plan"
    assert first["original_name"] == "plan.txt"
    assert first["mime_type"] == "text/plain"
    assert first["size_bytes"] == len(b"project 17 plan")
    assert first["content_hash"] == hashlib.sha256(b"project 17 plan").hexdigest()


def test_save_task_plan_attachment_rejects_pdf(tmp_path):
    with pytest.raises(TaskPlanProposalAttachmentError, match="not supported"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename="proposal.pdf", content=b"pdf"
        )


def test_save_task_plan_attachment_rejects_path_traversal_filename(tmp_path):
    with pytest.raises(TaskPlanProposalAttachmentError, match="basename"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename="../proposal.txt", content=b"text"
        )


def test_save_task_plan_attachment_rejects_empty_content(tmp_path):
    with pytest.raises(TaskPlanProposalAttachmentError, match="empty"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename="proposal.txt", content=b""
        )


def test_save_task_plan_attachment_rejects_content_over_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.task_plan_proposal_attachments.MAX_TASK_PLAN_ATTACHMENT_BYTES", 3
    )

    with pytest.raises(TaskPlanProposalAttachmentError, match="maximum"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename="proposal.txt", content=b"four"
        )


def test_remove_task_plan_attachment_removes_only_safe_stored_file(tmp_path):
    root = tmp_path / "attachments"
    saved = save_task_plan_attachment(
        root, project_id=1, filename="proposal.docx", content=b"document"
    )

    remove_task_plan_attachment(root, saved["storage_key"])
    remove_task_plan_attachment(root, saved["storage_key"])

    assert not saved["path"].exists()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"keep")
    with pytest.raises(TaskPlanProposalAttachmentError, match="outside"):
        remove_task_plan_attachment(root, "../outside.txt")
    assert outside.read_bytes() == b"keep"
