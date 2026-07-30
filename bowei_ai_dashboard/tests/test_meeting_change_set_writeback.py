from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "ALLOW_DEV_SCHEMA_CREATE_ALL",
        "ALLOW_PROTECTED_DATABASE_MIGRATION",
        "ALLOW_TEST_MEMORY_DATABASE",
        "DATABASE_URL",
        "PROTECTED_DATABASE_PATHS",
    ):
        env.pop(key, None)
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}",
            "PROTECTED_DATABASE_PATHS": str(
                (BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()
            ),
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_meeting_change_set_migration_contract(tmp_path: Path):
    database = tmp_path / "meeting-change-set.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "meeting_change_sets" in inspector.get_table_names()
    assert "meeting_change_proposals" in inspector.get_table_names()

    assert {
        column["name"]
        for column in inspector.get_columns("meeting_change_sets")
    } == {
        "id",
        "project_id",
        "meeting_id",
        "created_by_person_id",
        "transcript_hash",
        "snapshot_json",
        "result_json",
        "status",
        "created_at",
        "updated_at",
    }

    assert {
        column["name"]
        for column in inspector.get_columns("meeting_change_proposals")
    } == {
        "id",
        "change_set_id",
        "action",
        "target_type",
        "target_id",
        "parent_workstream_id",
        "before_json",
        "proposed_json",
        "evidence_json",
        "reason",
        "confidence",
        "validation_json",
        "execution_status",
        "executed_by_person_id",
        "executed_at",
        "result_target_id",
        "created_at",
        "updated_at",
    }

    change_set_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("meeting_change_sets")
    }
    proposal_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("meeting_change_proposals")
    }
    assert ("project_id", "status") in change_set_indexes
    assert ("meeting_id",) in change_set_indexes
    assert ("change_set_id", "execution_status") in proposal_indexes

    change_set_foreign_keys = {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in inspector.get_foreign_keys("meeting_change_sets")
    }
    proposal_foreign_keys = {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in inspector.get_foreign_keys("meeting_change_proposals")
    }
    assert (("project_id",), "projects") in change_set_foreign_keys
    assert (("meeting_id",), "meetings") in change_set_foreign_keys
    assert (("change_set_id",), "meeting_change_sets") in proposal_foreign_keys


def test_deleting_attached_meeting_preserves_change_set_and_clears_reference(
    tmp_path: Path,
):
    database = tmp_path / "meeting-delete.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    engine = sa.create_engine(f"sqlite:///{database.as_posix()}")

    @sa.event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    from app import models

    db = sessionmaker(bind=engine)()
    db.add(models.Project(id=1, name="Project A"))
    db.commit()
    db.add(models.Meeting(id=1, project_id=1, title="Attached meeting"))
    db.commit()
    db.add(
        models.MeetingChangeSet(
            id=1,
            project_id=1,
            meeting_id=1,
            transcript_hash="a" * 64,
            snapshot_json="{}",
            result_json="{}",
            status="attached",
        )
    )
    db.commit()

    db.delete(db.get(models.Meeting, 1))
    db.commit()
    db.expire_all()

    change_set = db.get(models.MeetingChangeSet, 1)
    assert change_set is not None
    assert change_set.meeting_id is None
