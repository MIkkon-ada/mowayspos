import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base


def _index_contract(table) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (index.name, tuple(column.name for column in index.columns))
        for index in table.indexes
    }


def _foreign_key_targets(table, column_name: str) -> set[str]:
    return {foreign_key.target_fullname for foreign_key in table.c[column_name].foreign_keys}


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


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
    assert _index_contract(attachment) == {
        ("ix_project_init_attachments_id", ("id",)),
        ("ix_project_init_attachments_project_id", ("project_id",)),
        ("ix_project_init_attachments_uploaded_by", ("uploaded_by",)),
        (
            "ix_project_init_attachments_uploaded_by_person_id",
            ("uploaded_by_person_id",),
        ),
        ("ix_project_init_attachments_deleted_at", ("deleted_at",)),
    }


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
    expected_defaults = {
        "attachment_ids_json": "[]",
        "current_draft_json": "[]",
        "status": "queued",
        "stage": "reading",
        "progress": 0,
        "result_json": "{}",
        "file_results_json": "[]",
        "error_summary": "",
        "provider": "",
        "model_name": "",
    }
    for column_name, expected in expected_defaults.items():
        assert run.c[column_name].default.arg == expected
    assert run.c.created_by.default is None
    assert run.c.created_by.nullable is False
    assert _index_contract(run) == {
        ("ix_project_init_analysis_runs_id", ("id",)),
        ("ix_project_init_analysis_runs_project_id", ("project_id",)),
        ("ix_project_init_analysis_runs_status", ("status",)),
        ("ix_project_init_analysis_runs_created_by", ("created_by",)),
        (
            "ix_project_init_analysis_runs_created_by_person_id",
            ("created_by_person_id",),
        ),
        ("uq_project_init_analysis_runs_retry_of", ("retry_of_run_id",)),
    }


def test_project_init_analysis_run_defaults_survive_orm_insert_round_trip():
    db = _make_session()
    project = models.Project(name="Project init AI defaults")
    db.add(project)
    db.flush()
    analysis_run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        created_by="owner",
    )
    db.add(analysis_run)
    db.flush()
    run_id = analysis_run.id
    db.expire_all()

    stored = db.get(models.ProjectInitAnalysisRun, run_id)

    assert stored is not None
    assert stored.attachment_ids_json == "[]"
    assert stored.current_draft_json == "[]"
    assert stored.status == "queued"
    assert stored.stage == "reading"
    assert stored.progress == 0
    assert stored.result_json == "{}"
    assert stored.file_results_json == "[]"
    assert stored.error_summary == ""
    assert stored.provider == ""
    assert stored.model_name == ""
    assert stored.created_by == "owner"
    assert stored.created_by_person_id is None
    assert stored.applied_at is None
    assert stored.created_at is not None
    assert stored.updated_at is not None


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


@pytest.mark.parametrize(
    "invalid_attachment_id",
    [True, "1", 1.0, 0, -1],
    ids=["bool", "string", "float", "zero", "negative"],
)
def test_project_init_analysis_create_rejects_non_strict_positive_attachment_ids(
    invalid_attachment_id,
):
    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisCreate(attachment_ids=[invalid_attachment_id])


def test_project_init_analysis_create_rejects_duplicate_attachment_ids():
    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisCreate(attachment_ids=[1, 1])


def test_project_init_analysis_action_accepts_only_retry_or_applied():
    assert schemas.ProjectInitAnalysisAction(action="retry").action == "retry"
    assert schemas.ProjectInitAnalysisAction(action="applied").action == "applied"

    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisAction(action="cancel")
