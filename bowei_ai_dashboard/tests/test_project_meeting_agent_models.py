from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PRE_AGENT_AUDIT_REVISION = "a1b2c3d4e5f6"
AGENT_AUDIT_REVISION = "c4e5f6a7b8c9"
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


def _migration_env(database: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        env.pop(key, None)
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "PROTECTED_DATABASE_PATHS": str((BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()),
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return env


def _run_alembic(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=_migration_env(database),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _alembic_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _database_revision(engine) -> str:
    with engine.connect() as connection:
        return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_project_meeting_run_has_agent_audit_columns():
    expected = {
        "stage", "step_count", "prompt_version", "model_code",
        "invocation_log_ids_json", "tool_trace_json", "raw_responses_json",
        "error_code",
    }
    columns = set(models.ProjectMeetingRun.__table__.columns.keys())
    assert expected <= columns
    assert {"validation_json", "requested_meeting_type"}.isdisjoint(columns)


def test_project_meeting_run_agent_defaults_survive_insert(db: Session):
    project = models.Project(name="AI Upgrade", status="active", is_active=True)
    db.add(project)
    db.flush()
    source = models.MeetingDocumentSource(
        project_id=project.id,
        original_name="minutes.docx",
        storage_key="test/minutes.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=1,
        content_hash="a" * 64,
    )
    db.add(source)
    db.flush()

    run = models.ProjectMeetingRun(project_id=project.id, document_source_id=source.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    assert run.stage == "created"
    assert run.step_count == 0
    assert run.invocation_log_ids_json == "[]"
    assert run.tool_trace_json == "[]"
    assert run.raw_responses_json == "[]"
    assert run.error_code == ""


def test_meeting_change_proposal_has_subtask_parent_column():
    column = models.MeetingChangeProposal.__table__.columns["parent_subtask_id"]
    assert column.nullable is True
    assert list(column.foreign_keys)[0].target_fullname == "subtasks.id"


def test_meeting_change_proposal_retains_workstream_parent_column():
    column = models.MeetingChangeProposal.__table__.columns["parent_workstream_id"]
    assert column.nullable is True
    assert list(column.foreign_keys)[0].target_fullname == "tasks.id"


def test_agent_audit_migration_has_the_expected_linear_revision_chain():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "b2c3d4e5f6a7_add_project_meeting_agent_audit.py"
    )
    module_spec = importlib.util.spec_from_file_location("project_meeting_agent_audit", migration_path)
    assert module_spec and module_spec.loader
    migration = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(migration)

    assert migration.revision == "c4e5f6a7b8c9"
    assert migration.down_revision == "a1b2c3d4e5f6"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_migration_chain_has_one_head_and_contains_agent_audit_and_lineage():
    app_root = Path(__file__).resolve().parents[1]
    config = Config(str(app_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    revisions = {revision.revision for revision in script.walk_revisions()}
    assert len(heads) == 1
    assert AGENT_AUDIT_REVISION in revisions
    assert "d5e6f7a8b9c0" in revisions


def test_agent_audit_migration_operations_are_parseable():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "b2c3d4e5f6a7_add_project_meeting_agent_audit.py"
    )
    tree = ast.parse(migration_path.read_text(encoding="utf-8"))
    function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"upgrade", "downgrade"} <= function_names


def test_agent_audit_migration_upgrades_and_downgrades_sqlite_schema(tmp_path: Path):
    database = tmp_path / "project-meeting-agent-audit.db"
    url = _sqlite_url(database)

    result = _run_alembic(database, "upgrade", PRE_AGENT_AUDIT_REVISION)
    assert result.returncode == 0, _alembic_output(result)

    engine = create_engine(url)
    before = sa.inspect(engine)
    assert _database_revision(engine) == PRE_AGENT_AUDIT_REVISION
    assert {
        "stage",
        "step_count",
        "prompt_version",
        "model_code",
        "invocation_log_ids_json",
        "tool_trace_json",
        "raw_responses_json",
        "error_code",
    }.isdisjoint({column["name"] for column in before.get_columns("project_meeting_runs")})
    assert "parent_subtask_id" not in {
        column["name"] for column in before.get_columns("meeting_change_proposals")
    }

    result = _run_alembic(database, "upgrade", AGENT_AUDIT_REVISION)
    assert result.returncode == 0, _alembic_output(result)

    upgraded = sa.inspect(engine)
    assert _database_revision(engine) == AGENT_AUDIT_REVISION
    assert {
        "stage",
        "step_count",
        "prompt_version",
        "model_code",
        "invocation_log_ids_json",
        "tool_trace_json",
        "raw_responses_json",
        "error_code",
    } <= {column["name"] for column in upgraded.get_columns("project_meeting_runs")}
    assert {index["name"] for index in upgraded.get_indexes("project_meeting_runs")} >= {
        "ix_project_meeting_runs_stage",
        "ix_project_meeting_runs_error_code",
    }
    assert "parent_subtask_id" in {
        column["name"] for column in upgraded.get_columns("meeting_change_proposals")
    }
    assert {index["name"] for index in upgraded.get_indexes("meeting_change_proposals")} >= {
        "ix_meeting_change_proposals_parent_subtask_id",
    }
    assert {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in upgraded.get_foreign_keys("meeting_change_proposals")
    } >= {(("parent_subtask_id",), "subtasks")}

    result = _run_alembic(database, "downgrade", PRE_AGENT_AUDIT_REVISION)
    assert result.returncode == 0, _alembic_output(result)

    downgraded = sa.inspect(engine)
    assert _database_revision(engine) == PRE_AGENT_AUDIT_REVISION
    assert {
        "stage",
        "step_count",
        "prompt_version",
        "model_code",
        "invocation_log_ids_json",
        "tool_trace_json",
        "raw_responses_json",
        "error_code",
    }.isdisjoint({column["name"] for column in downgraded.get_columns("project_meeting_runs")})
    assert {
        "ix_project_meeting_runs_stage",
        "ix_project_meeting_runs_error_code",
    }.isdisjoint({index["name"] for index in downgraded.get_indexes("project_meeting_runs")})
    assert "parent_subtask_id" not in {
        column["name"] for column in downgraded.get_columns("meeting_change_proposals")
    }
    assert "ix_meeting_change_proposals_parent_subtask_id" not in {
        index["name"] for index in downgraded.get_indexes("meeting_change_proposals")
    }
    assert (("parent_subtask_id",), "subtasks") not in {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in downgraded.get_foreign_keys("meeting_change_proposals")
    }
