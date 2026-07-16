from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

from app import models as _models  # noqa: F401 - register all existing tables
from app.database import Base


OLD_HEAD = "4bf512ac2391"
NEW_REVISION = "a7d9c3e5f102"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROTECTED_DATABASE = BACKEND_ROOT / "bowei_ai_dashboard.db"
SAFETY_ENV_KEYS = (
    "ALLOW_DEV_SCHEMA_CREATE_ALL",
    "ALLOW_PROTECTED_DATABASE_MIGRATION",
    "ALLOW_TEST_MEMORY_DATABASE",
    "APP_ENV",
    "BOWEI_DEV_MODE",
    "DATABASE_URL",
    "PROTECTED_DATABASE_PATHS",
)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _child_env(database: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        env.pop(key, None)
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "PROTECTED_DATABASE_PATHS": str(PROTECTED_DATABASE.resolve()),
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return env


def _run_alembic(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=_child_env(database),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _prepare_old_head_database(path: Path) -> str:
    url = _sqlite_url(path)
    engine = sa.create_engine(url)
    old_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != "project_close_requests"
    ]
    Base.metadata.create_all(engine, tables=old_tables)
    result = _run_alembic(path, "stamp", OLD_HEAD)
    assert result.returncode == 0, _output(result)
    return url


def test_migration_upgrade_creates_expected_table_columns_indexes_and_foreign_keys(tmp_path: Path):
    database = tmp_path / "upgrade.db"
    url = _prepare_old_head_database(database)
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    output = _output(result)
    assert "DATABASE TARGET" in output
    assert str(database.resolve()) in output

    engine = sa.create_engine(url)
    inspector = sa.inspect(engine)
    assert "project_close_requests" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("project_close_requests")} == {
        "id",
        "project_id",
        "requester_person_id",
        "summary",
        "objective_result",
        "unfinished_items_json",
        "remaining_risks_json",
        "handover_plan",
        "retrospective",
        "status",
        "reviewer_person_id",
        "review_comment",
        "created_at",
        "updated_at",
        "reviewed_at",
        "cancelled_at",
    }
    assert {tuple(index["column_names"]) for index in inspector.get_indexes("project_close_requests")} >= {
        ("id",),
        ("project_id",),
        ("requester_person_id",),
        ("reviewer_person_id",),
        ("status",),
    }
    assert {
        (tuple(fk["constrained_columns"]), fk["referred_table"])
        for fk in inspector.get_foreign_keys("project_close_requests")
    } >= {
        (("project_id",), "projects"),
        (("requester_person_id",), "people"),
        (("reviewer_person_id",), "people"),
    }

    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == NEW_REVISION
        assert conn.execute(sa.text("PRAGMA integrity_check")).scalar_one() == "ok"


def test_migration_empty_downgrade_and_reupgrade_succeed(tmp_path: Path):
    database = tmp_path / "roundtrip.db"
    url = _prepare_old_head_database(database)
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    result = _run_alembic(database, "downgrade", OLD_HEAD)
    assert result.returncode == 0, _output(result)
    assert "project_close_requests" not in sa.inspect(sa.create_engine(url)).get_table_names()

    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    assert "project_close_requests" in sa.inspect(sa.create_engine(url)).get_table_names()


def test_migration_downgrade_refuses_when_close_request_data_exists(tmp_path: Path):
    database = tmp_path / "protected-request.db"
    url = _prepare_old_head_database(database)
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO projects (id,name,status,is_active) VALUES (1,'P','active',1)"))
        conn.execute(sa.text("""
            INSERT INTO project_close_requests (
                project_id, summary, objective_result, unfinished_items_json,
                remaining_risks_json, handover_plan, retrospective, status
            ) VALUES (1,'s','o','[]','[]','h','r','pending')
        """))

    result = _run_alembic(database, "downgrade", OLD_HEAD)
    assert result.returncode != 0
    assert "project_close_requests contains data" in _output(result)


@pytest.mark.parametrize("status", ["pending_close", "ended"])
def test_migration_downgrade_refuses_when_projects_use_new_status(tmp_path: Path, status: str):
    database = tmp_path / f"protected-{status}.db"
    url = _prepare_old_head_database(database)
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO projects (id,name,status,is_active) VALUES (1,'P',:status,0)"),
            {"status": status},
        )

    result = _run_alembic(database, "downgrade", OLD_HEAD)
    assert result.returncode != 0
    assert "projects still use pending_close or ended" in _output(result)
