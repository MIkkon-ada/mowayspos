import pytest
from pydantic import ValidationError

from app import models, schemas


def _indexed_columns(table) -> set[str]:
    return {
        column.name
        for index in table.indexes
        for column in index.columns
    }


def _foreign_key_targets(table, column_name: str) -> set[str]:
    return {foreign_key.target_fullname for foreign_key in table.c[column_name].foreign_keys}


def test_project_init_attachment_has_storage_audit_fields_and_indexes():
    attachment = models.ProjectInitAttachment.__table__

    assert attachment.name == "project_init_attachments"
    assert {
        "project_id",
        "storage_key",
        "original_name",
        "mime_type",
        "size_bytes",
        "uploaded_by",
        "uploaded_by_person_id",
        "deleted_at",
        "deleted_by",
    } <= set(attachment.c.keys())
    assert attachment.c.storage_key.unique
    assert _foreign_key_targets(attachment, "project_id") == {"projects.id"}
    assert _foreign_key_targets(attachment, "uploaded_by_person_id") == {"people.id"}
    assert {
        "id",
        "project_id",
        "uploaded_by",
        "uploaded_by_person_id",
        "deleted_at",
    } <= _indexed_columns(attachment)


def test_project_init_analysis_run_has_snapshot_result_audit_fields_and_defaults():
    run = models.ProjectInitAnalysisRun.__table__

    assert run.name == "project_init_analysis_runs"
    assert {
        "project_id",
        "attachment_ids_json",
        "current_draft_json",
        "status",
        "stage",
        "progress",
        "result_json",
        "file_results_json",
        "error_summary",
        "provider",
        "model_name",
        "created_by",
        "created_by_person_id",
        "applied_at",
    } <= set(run.c.keys())
    assert _foreign_key_targets(run, "project_id") == {"projects.id"}
    assert _foreign_key_targets(run, "created_by_person_id") == {"people.id"}
    assert run.c.status.default.arg == "queued"
    assert run.c.progress.default.arg == 0
    assert {
        "id",
        "project_id",
        "status",
        "created_by",
        "created_by_person_id",
    } <= _indexed_columns(run)


@pytest.mark.parametrize("attachment_count", [1, 10])
def test_project_init_analysis_create_accepts_one_to_ten_attachments(attachment_count):
    payload = schemas.ProjectInitAnalysisCreate(
        attachment_ids=list(range(1, attachment_count + 1)),
        current_draft=[schemas.ProjectWorkProgressTaskDraft(title="Implementation")],
    )

    assert len(payload.attachment_ids) == attachment_count
    assert payload.current_draft[0].title == "Implementation"


@pytest.mark.parametrize("attachment_count", [0, 11])
def test_project_init_analysis_create_rejects_attachment_counts_outside_limit(
    attachment_count,
):
    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisCreate(
            attachment_ids=list(range(1, attachment_count + 1)),
            current_draft=[],
        )


def test_project_init_analysis_action_accepts_only_retry_or_applied():
    assert schemas.ProjectInitAnalysisAction(action="retry").action == "retry"
    assert schemas.ProjectInitAnalysisAction(action="applied").action == "applied"

    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisAction(action="cancel")
