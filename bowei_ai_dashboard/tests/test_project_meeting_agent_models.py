from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import Base


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


def test_agent_audit_migration_is_the_only_alembic_head():
    app_root = Path(__file__).resolve().parents[1]
    config = Config(str(app_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["c4e5f6a7b8c9"]


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
