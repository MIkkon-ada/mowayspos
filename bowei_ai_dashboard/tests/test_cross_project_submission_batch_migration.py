from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).resolve().parents[1]
OLD_HEAD = "c8e4f2a7d901"
NEW_HEAD = "e2b7c4d9a610"
IDENTITY_HEAD = "n5o6p7q8r9s0"
PAYLOAD_HASH_HEAD = "o6p7q8r9s0t1"
SINGLE_REQUEST_HEAD = "p7q8r9s0t1u2"
TASK_REQUEST_HEAD = "q8r9s0t1u2v3"
ISSUE_REQUEST_HEAD = "r9s0t1u2v3w4"
ACHIEVEMENT_REQUEST_HEAD = "s0t1u2v3w4x5"
MEETING_REQUEST_HEAD = "t1u2v3w4x5y6"
CLOSE_REQUEST_HEAD = "u2v3w4x5y6z7"
PROJECT_CREATE_REQUEST_HEAD = "v3w4x5y6z7a8"
PROJECT_BATCH_IMPORT_HEAD = "w4x5y6z7a8b9"
ACHIEVEMENT_SUBMISSION_REQUEST_HEAD = "x5y6z7a8b9c0"


def _run(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "ALLOW_DEV_SCHEMA_CREATE_ALL", "ALLOW_PROTECTED_DATABASE_MIGRATION",
        "ALLOW_TEST_MEMORY_DATABASE", "DATABASE_URL", "PROTECTED_DATABASE_PATHS",
    ):
        env.pop(key, None)
    env.update({
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}",
        "PROTECTED_DATABASE_PATHS": str((BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()),
        "PYTHONPATH": str(BACKEND_ROOT),
    })
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def test_batch_migration_upgrade_contract(tmp_path: Path):
    database = tmp_path / "batch.db"
    _assert_ok(_run(database, "upgrade", NEW_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))

    assert "update_submission_batches" in inspector.get_table_names()
    assert {c["name"] for c in inspector.get_columns("update_submission_batches")} == {
        "id", "client_request_id", "submitter", "submitter_id", "source_type",
        "title", "transcript_text", "submission_count", "created_at", "updated_at",
    }
    assert {c["name"] for c in inspector.get_columns("update_submissions")} >= {
        "batch_id", "batch_order",
    }
    assert any(i.get("unique") and i["column_names"] == ["client_request_id"]
               for i in inspector.get_indexes("update_submission_batches"))
    assert any(fk["constrained_columns"] == ["batch_id"]
               and fk["referred_table"] == "update_submission_batches"
               for fk in inspector.get_foreign_keys("update_submissions"))


def test_batch_migration_round_trip(tmp_path: Path):
    database = tmp_path / "roundtrip.db"
    _assert_ok(_run(database, "upgrade", NEW_HEAD))
    _assert_ok(_run(database, "downgrade", OLD_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "update_submission_batches" not in inspector.get_table_names()
    assert "batch_id" not in {c["name"] for c in inspector.get_columns("update_submissions")}
    _assert_ok(_run(database, "upgrade", NEW_HEAD))


def test_batch_orm_contract():
    from app import models

    assert models.UpdateSubmissionBatch.__tablename__ == "update_submission_batches"
    assert models.UpdateSubmission.__table__.c.batch_id.nullable is True
    assert models.UpdateSubmission.__table__.c.batch_order.default.arg == 0


def test_batch_payload_hash_migration_round_trip(tmp_path: Path):
    database = tmp_path / "batch-payload-hash.db"
    _assert_ok(_run(database, "upgrade", IDENTITY_HEAD))
    _assert_ok(_run(database, "upgrade", PAYLOAD_HASH_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "request_payload_hash" in {
        column["name"] for column in inspector.get_columns("update_submission_batches")
    }

    _assert_ok(_run(database, "downgrade", IDENTITY_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "request_payload_hash" not in {
        column["name"] for column in inspector.get_columns("update_submission_batches")
    }


def test_single_submission_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "single-submission-idempotency.db"
    _assert_ok(_run(database, "upgrade", PAYLOAD_HASH_HEAD))
    _assert_ok(_run(database, "upgrade", SINGLE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("update_submissions")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("update_submissions")
    )

    _assert_ok(_run(database, "downgrade", PAYLOAD_HASH_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("update_submissions")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns


def test_task_create_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "task-create-idempotency.db"
    _assert_ok(_run(database, "upgrade", TASK_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("tasks")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("tasks")
    )

    _assert_ok(_run(database, "downgrade", SINGLE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("tasks")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.Task.__table__.c.client_request_id.unique is True
    assert models.Task.__table__.c.client_request_id.info["api_exclude"] is True


def test_issue_create_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "issue-create-idempotency.db"
    _assert_ok(_run(database, "upgrade", TASK_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", ISSUE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("issues")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("issues")
    )

    _assert_ok(_run(database, "downgrade", TASK_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("issues")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.Issue.__table__.c.client_request_id.unique is True
    assert models.Issue.__table__.c.client_request_id.info["api_exclude"] is True


def test_achievement_create_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "achievement-create-idempotency.db"
    _assert_ok(_run(database, "upgrade", ISSUE_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", ACHIEVEMENT_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("achievements")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("achievements")
    )

    _assert_ok(_run(database, "downgrade", ISSUE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("achievements")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.Achievement.__table__.c.client_request_id.unique is True
    assert models.Achievement.__table__.c.client_request_id.info["api_exclude"] is True


def test_meeting_create_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "meeting-create-idempotency.db"
    _assert_ok(_run(database, "upgrade", ACHIEVEMENT_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", MEETING_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("meetings")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("meetings")
    )

    _assert_ok(_run(database, "downgrade", ACHIEVEMENT_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("meetings")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.Meeting.__table__.c.client_request_id.unique is True
    assert models.Meeting.__table__.c.client_request_id.info["api_exclude"] is True


def test_project_close_request_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "project-close-request-idempotency.db"
    _assert_ok(_run(database, "upgrade", MEETING_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", CLOSE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("project_close_requests")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("project_close_requests")
    )

    _assert_ok(_run(database, "downgrade", MEETING_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("project_close_requests")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.ProjectCloseRequest.__table__.c.client_request_id.unique is True
    assert models.ProjectCloseRequest.__table__.c.client_request_id.info["api_exclude"] is True


def test_project_create_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "project-create-idempotency.db"
    _assert_ok(_run(database, "upgrade", CLOSE_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", PROJECT_CREATE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("projects")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("projects")
    )

    _assert_ok(_run(database, "downgrade", CLOSE_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("projects")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.Project.__table__.c.client_request_id.unique is True
    assert models.Project.__table__.c.client_request_id.info["api_exclude"] is True


def test_project_batch_import_retry_migration_round_trip(tmp_path: Path):
    database = tmp_path / "project-batch-import-idempotency.db"
    _assert_ok(_run(database, "upgrade", PROJECT_CREATE_REQUEST_HEAD))
    _assert_ok(_run(database, "upgrade", PROJECT_BATCH_IMPORT_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "project_batch_imports" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("project_batch_imports")}
    assert {"id", "client_request_id", "request_payload_hash", "result_json", "created_at", "updated_at"} == columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("project_batch_imports")
    )

    _assert_ok(_run(database, "downgrade", PROJECT_CREATE_REQUEST_HEAD))
    assert "project_batch_imports" not in sa.inspect(
        sa.create_engine(f"sqlite:///{database.as_posix()}")
    ).get_table_names()

    from app import models

    assert models.ProjectBatchImport.__tablename__ == "project_batch_imports"
    assert models.ProjectBatchImport.__table__.c.client_request_id.unique is True


def test_achievement_submission_idempotency_migration_round_trip(tmp_path: Path):
    database = tmp_path / "achievement-submission-idempotency.db"
    _assert_ok(_run(database, "upgrade", PROJECT_BATCH_IMPORT_HEAD))
    _assert_ok(_run(database, "upgrade", ACHIEVEMENT_SUBMISSION_REQUEST_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("achievement_submissions")}
    assert {"client_request_id", "request_payload_hash"} <= columns
    assert any(
        index.get("unique") and index["column_names"] == ["client_request_id"]
        for index in inspector.get_indexes("achievement_submissions")
    )

    _assert_ok(_run(database, "downgrade", PROJECT_BATCH_IMPORT_HEAD))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("achievement_submissions")}
    assert "client_request_id" not in columns
    assert "request_payload_hash" not in columns

    from app import models

    assert models.AchievementSubmission.__table__.c.client_request_id.unique is True
    assert models.AchievementSubmission.__table__.c.client_request_id.info["api_exclude"] is True
