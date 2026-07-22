from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).resolve().parents[1]
OLD_HEAD = "c8e4f2a7d901"
NEW_HEAD = "e2b7c4d9a610"


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
