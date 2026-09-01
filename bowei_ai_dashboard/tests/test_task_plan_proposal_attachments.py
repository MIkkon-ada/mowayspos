import hashlib
from pathlib import Path

import pytest

from app.services.task_plan_proposal_attachments import (
    MAX_TASK_PLAN_ATTACHMENT_BYTES,
    MAX_TASK_PLAN_ATTACHMENT_COUNT,
    TaskPlanProposalAttachmentError,
    remove_task_plan_attachment,
    save_task_plan_attachment,
    save_task_plan_attachments,
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


@pytest.mark.parametrize("project_id", [0, -1, True])
def test_save_task_plan_attachment_rejects_non_positive_project_id(tmp_path, project_id):
    with pytest.raises(TaskPlanProposalAttachmentError, match="positive integer"):
        save_task_plan_attachment(
            tmp_path, project_id=project_id, filename="proposal.txt", content=b"text"
        )


@pytest.mark.parametrize(
    ("filename", "expected_mime"),
    [
        ("proposal.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("proposal.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_save_task_plan_attachment_allows_office_file_types(tmp_path, filename, expected_mime):
    saved = save_task_plan_attachment(
        tmp_path, project_id=1, filename=filename, content=b"office document"
    )

    assert saved["mime_type"] == expected_mime
    assert saved["path"].read_bytes() == b"office document"


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


def test_save_task_plan_attachment_accepts_exact_10_mib_limit(tmp_path):
    content = b"x" * MAX_TASK_PLAN_ATTACHMENT_BYTES

    saved = save_task_plan_attachment(
        tmp_path, project_id=1, filename="proposal.txt", content=content
    )

    assert saved["size_bytes"] == MAX_TASK_PLAN_ATTACHMENT_BYTES
    assert saved["path"].stat().st_size == MAX_TASK_PLAN_ATTACHMENT_BYTES


def test_save_task_plan_attachments_rejects_eleventh_file_before_writing(tmp_path):
    attachments = [("proposal-11.txt", b"text")]

    with pytest.raises(TaskPlanProposalAttachmentError, match="maximum count"):
        save_task_plan_attachments(
            tmp_path,
            project_id=1,
            attachments=attachments,
            existing_attachment_count=MAX_TASK_PLAN_ATTACHMENT_COUNT,
        )

    assert not list(tmp_path.rglob("*"))


def test_save_task_plan_attachments_prevalidates_all_files_before_writing(tmp_path):
    root = tmp_path / "attachments"

    with pytest.raises(TaskPlanProposalAttachmentError, match="not supported"):
        save_task_plan_attachments(
            root,
            project_id=1,
            attachments=[("valid.txt", b"valid"), ("invalid.pdf", b"pdf")],
        )

    assert not [path for path in root.rglob("*") if path.is_file()]


def test_save_task_plan_attachments_removes_files_when_second_write_fails(monkeypatch, tmp_path):
    root = tmp_path / "attachments"
    original_write_bytes = Path.write_bytes
    write_attempts = 0

    def fail_second_write(path, content):
        nonlocal write_attempts
        write_attempts += 1
        if write_attempts == 2:
            raise OSError("disk unavailable")
        return original_write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail_second_write)

    with pytest.raises(OSError, match="disk unavailable"):
        save_task_plan_attachments(
            root,
            project_id=1,
            attachments=[("first.txt", b"first"), ("second.txt", b"second")],
        )

    assert not [path for path in root.rglob("*") if path.is_file()]


def test_save_task_plan_attachment_rejects_filename_over_model_limit(tmp_path):
    filename = f"{'a' * 252}.txt"

    with pytest.raises(TaskPlanProposalAttachmentError, match="too long"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename=filename, content=b"text"
        )


def test_save_task_plan_attachment_rejects_control_character_in_filename(tmp_path):
    with pytest.raises(TaskPlanProposalAttachmentError, match="control character"):
        save_task_plan_attachment(
            tmp_path, project_id=1, filename="bad\nname.txt", content=b"text"
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
