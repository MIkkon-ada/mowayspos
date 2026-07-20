from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, MetaData, String, Table, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "migrate_sqlite_to_postgres.py"
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"
DOCUMENT_PATH = REPO_ROOT / "docs" / "sqlite-to-postgres-data-migration.md"
PROJECT_PROFILE_REVISION = "c8e4f2a7d901"
PROJECT_PROFILE_DOWN_REVISION = "a7d9c3e5f102"
PROJECT_PROFILE_COLUMNS = {
    "project_type", "client_name", "background", "objectives", "expected_outcomes",
    "lifecycle_status", "kickoff_date", "kickoff_by", "initiated_by",
}
ARCHIVE_ONLY_COLUMNS = {
    "achievements.is_desensitized", "issues.feedback_required", "people.employee_code",
    "people.permission_scope", "people.title", "update_submissions.workflow_status",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("sqlite_to_postgres_migration", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": database_url})
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_CONFIG), *args],
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _build_source_database(path: Path) -> Path:
    result = _run_alembic(_sqlite_url(path), "upgrade", "head")
    assert result.returncode == 0, _output(result)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE achievements ADD COLUMN is_desensitized BOOLEAN DEFAULT 0")
        connection.execute("ALTER TABLE issues ADD COLUMN feedback_required BOOLEAN DEFAULT 0")
        connection.execute("ALTER TABLE people ADD COLUMN employee_code TEXT DEFAULT ''")
        connection.execute("ALTER TABLE people ADD COLUMN permission_scope TEXT DEFAULT ''")
        connection.execute("ALTER TABLE people ADD COLUMN title TEXT DEFAULT ''")
        connection.execute("ALTER TABLE update_submissions ADD COLUMN workflow_status TEXT DEFAULT ''")
        connection.execute("ALTER TABLE update_submissions ADD COLUMN ceo_decision_required BOOLEAN DEFAULT 0")
        connection.execute(
            "INSERT INTO people "
            "(id, name, system_role, is_active, is_admin, employee_code, permission_scope, title, "
            "created_at, updated_at) VALUES (10, 'Migration Admin', 'super_admin', 1, 1, "
            "'FIXTURE-001', 'all', 'Legacy Admin Title', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO accounts "
            "(id, username, password_hash, person_id, status, is_tech_admin, "
            "must_change_password, last_password_changed_at, created_at, updated_at) "
            "VALUES (20, 'migration-admin', 'fixture-password-hash-secret', 10, "
            "'active', 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO platform_settings (id, data_json, created_at, updated_at) "
            "VALUES (1, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO projects "
            "(id, name, status, is_active, project_type, client_name, background, objectives, "
            "expected_outcomes, lifecycle_status, kickoff_date, kickoff_by, initiated_by, "
            "created_at, updated_at) VALUES (30, 'Migration Fixture Project', 'active', 1, "
            "'internal', 'Fixture Client', 'Fixture Background', 'Fixture Objectives', "
            "'Fixture Outcomes', 'active', '2026-01-02', 'Fixture Kickoff', "
            "'Fixture Initiator', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO project_members "
            "(id, project_id, person_id, person_name_snapshot, role, joined_at, created_at, updated_at) "
            "VALUES (40, 30, 10, 'Migration Admin', 'owner', CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO tasks "
            "(id, project_id, special_project, key_task, owner, owner_id, status, "
            "created_at, updated_at) VALUES (50, 30, 'Migration Fixture Project', "
            "'Fixture Workstream', 'Migration Admin', 10, '进行中', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO subtasks "
            "(id, task_id, title, assignee, assignee_id, status, created_at, updated_at) "
            "VALUES (60, 50, 'Fixture Key Task', 'Migration Admin', 10, '进行中', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO subtask_drafts "
            "(id, project_id, parent_task_id, title, proposer, assignee, assignee_id, "
            "status, created_at, updated_at) VALUES (61, 30, 50, 'Fixture Draft', "
            "'Migration Admin', 'Migration Admin', 10, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO update_submissions "
            "(id, project_id, source_type, submitter, submitter_id, title, transcript_text, "
            "ai_result_json, human_result_json, confirm_status, related_task_id, related_subtask_id, "
            "workflow_status, ceo_decision_required, "
            "created_at, updated_at) VALUES (70, 30, 'voice', 'Migration Admin', 10, "
            "'Fixture Update', 'private fixture transcript', '{}', '{\"task_reports\":[{\"confirmation_status\":\"confirmed\"}]}', '待确认', 50, 60, 'pending_owner', 0, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO meetings "
            "(id, project_id, meeting_type, title, transcript_text, created_at, updated_at) "
            "VALUES (80, 30, 'kickoff', 'Fixture Meeting', 'private meeting text', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO achievements "
            "(id, project_id, name, owner, owner_id, related_task_id, related_subtask_id, "
            "status, created_at, updated_at) VALUES (90, 30, 'Fixture Achievement', "
            "'Migration Admin', 10, 50, 60, '已入库', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO achievement_submissions "
            "(id, project_id, related_task_id, related_subtask_id, submitter, submitter_id, "
            "name, status, created_at, updated_at) VALUES (91, 30, 50, 60, "
            "'Migration Admin', 10, 'Fixture Achievement Submission', '待确认', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO issues "
            "(id, project_id, description, owner, owner_id, related_task_id, related_subtask_id, "
            "status, created_at, updated_at) VALUES (100, 30, 'private fixture issue', "
            "'Migration Admin', 10, 50, 60, '待处理', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO member_change_requests "
            "(id, project_id, requester_person_id, action, target_person_id, target_person_name, "
            "to_role, status, created_at, updated_at) VALUES (110, 30, 10, 'add', 10, "
            "'Migration Admin', 'member', 'approved', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO notifications "
            "(id, recipient, recipient_id, type, title, project_id, created_at) "
            "VALUES (120, 'Migration Admin', 10, 'fixture', 'Fixture Notification', 30, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO operation_logs "
            "(id, project_id, operator, action, target_type, target_id, note, created_at, updated_at) "
            "VALUES (130, 30, 'Migration Admin', 'fixture', 'project', 30, "
            "'private operation note', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO auth_sessions "
            "(session_id, session_token_hash, username, created_at, expires_at, last_seen_at) "
            "VALUES ('fixture-session', 'fixture-session-hash-secret', 'migration-admin', "
            "CURRENT_TIMESTAMP, DATETIME('now', '+1 day'), CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO login_attempts "
            "(id, username, success, failure_reason, ip_address, user_agent, created_at) "
            "VALUES (140, 'migration-admin', 0, 'fixture', '192.0.2.1', 'fixture-agent', CURRENT_TIMESTAMP)"
        )
        connection.commit()
    return path


@pytest.fixture(scope="session")
def postgres_server():
    name = f"moways-p1d0-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(32)
    result = subprocess.run(
        [
            "docker", "run", "-d", "--name", name,
            "-e", f"POSTGRES_PASSWORD={password}",
            "-e", "POSTGRES_USER=moways_migration",
            "-e", "POSTGRES_DB=postgres",
            "-p", "127.0.0.1::5432",
            "postgres:16-alpine",
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, _output(result)
    try:
        inspect = subprocess.run(
            ["docker", "port", name, "5432/tcp"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert inspect.returncode == 0, _output(inspect)
        port = int(inspect.stdout.strip().rsplit(":", 1)[1])
        admin_url = f"postgresql://moways_migration:{password}@127.0.0.1:{port}/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(admin_url, connect_timeout=2):
                    break
            except psycopg.OperationalError:
                time.sleep(0.5)
        else:
            logs = subprocess.run(
                ["docker", "logs", name], text=True, capture_output=True, timeout=30
            )
            pytest.fail(_output(logs))
        yield {"name": name, "admin_url": admin_url, "port": port, "password": password}
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )


@pytest.fixture
def postgres_database(postgres_server):
    database = f"migration_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_server["admin_url"], autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    url = (
        f"postgresql+psycopg://moways_migration:{postgres_server['password']}"
        f"@127.0.0.1:{postgres_server['port']}/{database}"
    )
    result = _run_alembic(url, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    try:
        yield url
    finally:
        with psycopg.connect(postgres_server["admin_url"], autocommit=True) as connection:
            connection.execute(
                sql.SQL("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = {} AND pid <> pg_backend_pid()").format(sql.Literal(database))
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.fixture
def source_database(tmp_path: Path) -> Path:
    return _build_source_database(tmp_path / "source.db")


def test_migration_script_exists():
    assert SCRIPT_PATH.is_file()


def test_operator_documentation_is_fail_closed_and_keeps_credentials_out_of_cli():
    content = DOCUMENT_PATH.read_text(encoding="utf-8")
    assert "--source-sqlite" in content
    assert "--dry-run" in content
    assert "--apply" in content
    assert "--report-json" in content
    assert "DATABASE_URL" in content
    assert "命令行参数" in content
    assert "auth_sessions" in content
    assert "login_attempts" in content
    assert "不得执行 Alembic" in content
    assert "目标业务表必须为空" in content
    assert "单一 PostgreSQL transaction" in content
    assert "腾讯云" in content


def test_cli_requires_exactly_one_mode_and_has_no_database_url_argument():
    module = _load_module()
    parser = module.build_parser()
    option_strings = {option for action in parser._actions for option in action.option_strings}
    assert "--source-sqlite" in option_strings
    assert "--dry-run" in option_strings
    assert "--apply" in option_strings
    assert "--report-json" in option_strings
    assert "--database-url" not in option_strings
    with pytest.raises(SystemExit):
        parser.parse_args(["--source-sqlite", "C:/source.db"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--source-sqlite", "C:/source.db", "--dry-run", "--apply"])


def test_source_must_be_absolute_sqlite_and_connection_is_read_only(tmp_path: Path):
    module = _load_module()
    path = tmp_path / "source.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    with pytest.raises(module.MigrationError, match="absolute"):
        module.validate_source_path(Path("relative.db"))
    invalid = tmp_path / "invalid.db"
    invalid.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(module.MigrationError, match="SQLite"):
        module.validate_source_path(invalid)
    with module.open_source_readonly(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO sample (id) VALUES (1)")


@pytest.mark.parametrize(
    ("value", "column_type", "expected"),
    [
        (1, Boolean(), True),
        ("false", Boolean(), False),
        ("2026-07-20T01:02:03", DateTime(), "datetime"),
        ('{"ok":true}', JSON(), {"ok": True}),
        ("42", Integer(), 42),
        ("unchanged", String(), "unchanged"),
        (None, String(), None),
    ],
)
def test_sqlite_values_are_validated_for_postgresql(value, column_type, expected):
    module = _load_module()
    converted = module.convert_value(value, column_type, table="sample", column="value")
    if expected == "datetime":
        assert converted.isoformat() == value
    else:
        assert converted == expected


def test_invalid_boolean_datetime_and_json_values_are_blocking():
    module = _load_module()
    for value, column_type in [(2, Boolean()), ("not-a-date", DateTime()), ("{bad", JSON())]:
        with pytest.raises(module.MigrationError, match="sample.value"):
            module.convert_value(value, column_type, table="sample", column="value")


def test_column_mapping_handles_nullable_defaults_required_and_source_only():
    module = _load_module()
    metadata = MetaData()
    table = Table(
        "sample", metadata,
        Column("id", Integer, primary_key=True),
        Column("nullable_value", String, nullable=True),
        Column("default_value", String, nullable=False, server_default="safe"),
        Column("required_value", String, nullable=False),
    )
    result = module.analyze_column_mapping(
        table,
        source_columns={"id", "source_only"},
        source_row_count=1,
        source_nonempty_counts={"source_only": 1},
    )
    assert result["insert_columns"] == ["id"]
    assert result["source_only"] == [{"column": "source_only", "nonempty_rows": 1}]
    assert {entry["column"] for entry in result["target_only"]} == {
        "nullable_value", "default_value", "required_value"
    }
    assert any("sample.source_only" in error for error in result["blocking_errors"])
    assert any("sample.required_value" in error for error in result["blocking_errors"])
    assert not any("nullable_value" in error for error in result["blocking_errors"])
    assert not any("default_value" in error for error in result["blocking_errors"])


def test_dependency_order_is_topological_and_cycles_fail_closed():
    module = _load_module()
    dependencies = {
        "people": set(),
        "accounts": {"people"},
        "projects": set(),
        "project_members": {"people", "projects"},
        "tasks": {"projects", "people"},
        "subtasks": {"tasks", "people"},
        "updates": {"projects", "tasks", "subtasks", "people"},
    }
    order = module.topological_order(dependencies)
    positions = {name: order.index(name) for name in order}
    assert positions["people"] < positions["accounts"]
    assert positions["projects"] < positions["project_members"]
    assert positions["tasks"] < positions["subtasks"] < positions["updates"]
    with pytest.raises(module.MigrationError, match="cycle"):
        module.topological_order({"one": {"two"}, "two": {"one"}})


def test_target_must_be_postgresql_and_url_is_never_rendered(tmp_path: Path):
    module = _load_module()
    sqlite_target = _sqlite_url(tmp_path / "target.db")
    with pytest.raises(module.MigrationError, match="PostgreSQL"):
        module.validate_target_url(sqlite_target)
    secret_url = "postgresql+psycopg://user:secret-password@db.example.test:5432/example"
    description = module.safe_target_description(secret_url)
    assert "secret-password" not in description
    assert secret_url not in description
    assert description == "postgresql://db.example.test:5432/example"


def test_dry_run_is_zero_write_and_report_is_sanitized(
    source_database: Path,
    postgres_database: str,
    tmp_path: Path,
    capsys,
):
    module = _load_module()
    source_before = (_sha256(source_database), source_database.stat().st_mtime_ns)
    report_path = tmp_path / "report.json"
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="dry-run",
        report_path=report_path,
    )
    source_after = (_sha256(source_database), source_database.stat().st_mtime_ns)
    assert source_after == source_before
    assert report["apply_allowed"] is True
    assert report["applied"] is False
    assert report["blocking_errors"] == []
    assert report["source"]["integrity_check"] == "ok"
    assert report["source"]["sha256"] == _sha256(source_database)
    assert report["excluded_tables"] == {
        "auth_sessions": "environment-specific authentication sessions are not portable",
        "login_attempts": "environment-specific login security history is not portable",
    }
    assert report["target"]["business_rows_before"] == 0
    assert report["estimated_rows"] > 0
    assert "people" in report["migration_order"]
    assert report["migration_order"].index("people") < report["migration_order"].index("accounts")
    payload = report_path.read_text(encoding="utf-8")
    output = capsys.readouterr().out
    for secret in (
        "fixture-password-hash-secret",
        "fixture-session-hash-secret",
        "private fixture transcript",
        "private fixture issue",
        "private meeting text",
        "private operation note",
        postgres_database,
    ):
        assert secret not in payload
        assert secret not in output
    parsed = json.loads(payload)
    assert parsed == report
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_target_nonempty_and_revision_mismatch_refuse_apply(
    source_database: Path,
    postgres_database: str,
):
    module = _load_module()
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        connection.execute(
            "INSERT INTO people (id, name, system_role, is_active, is_admin) "
            "VALUES (999, 'Existing', 'normal_member', true, false)"
        )
        connection.commit()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="dry-run",
    )
    assert report["apply_allowed"] is False
    assert any("target business tables are not empty" in error for error in report["blocking_errors"])
    with pytest.raises(module.MigrationError, match="Apply refused"):
        module.run_migration(
            source_path=source_database,
            target_url=postgres_database,
            mode="apply",
        )
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        connection.execute("DELETE FROM people")
        connection.execute("UPDATE alembic_version SET version_num = '4bf512ac2391'")
        connection.commit()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="dry-run",
    )
    assert report["apply_allowed"] is False
    assert any("target Alembic revision" in error for error in report["blocking_errors"])


def test_apply_preserves_ids_hashes_relationships_resets_sequences_and_rejects_repeat(
    source_database: Path,
    postgres_database: str,
):
    module = _load_module()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="apply",
    )
    assert report["applied"] is True
    assert report["verification"]["row_counts_match"] is True
    assert report["verification"]["tech_admin_count"] == 1
    assert report["verification"]["auth_sessions"] == 0
    assert report["verification"]["login_attempts"] == 0
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        assert connection.execute("SELECT id, person_id, password_hash FROM accounts").fetchone() == (
            20, 10, "fixture-password-hash-secret"
        )
        assert connection.execute("SELECT project_id, person_id FROM project_members").fetchone() == (30, 10)
        assert connection.execute("SELECT task_id, assignee_id FROM subtasks").fetchone() == (50, 10)
        max_id = connection.execute("SELECT MAX(id) FROM people").fetchone()[0]
        sequence = connection.execute(
            "SELECT pg_get_serial_sequence('people', 'id')"
        ).fetchone()[0]
        last_value = connection.execute(
            sql.SQL("SELECT last_value FROM {}").format(sql.Identifier(sequence.split(".")[-1]))
        ).fetchone()[0]
        assert last_value >= max_id
        new_id = connection.execute(
            "INSERT INTO people (name, system_role, is_active, is_admin) "
            "VALUES ('Sequence Check', 'normal_member', true, false) RETURNING id"
        ).fetchone()[0]
        assert new_id > max_id
        connection.rollback()
    with pytest.raises(module.MigrationError, match="Apply refused"):
        module.run_migration(
            source_path=source_database,
            target_url=postgres_database,
            mode="apply",
        )


def test_apply_rolls_back_every_table_when_one_insert_fails(
    source_database: Path,
    postgres_database: str,
    monkeypatch,
):
    module = _load_module()
    original = module._insert_table

    def fail_on_tasks(*args, **kwargs):
        table_name = kwargs.get("table_name") or args[2]
        if table_name == "tasks":
            raise RuntimeError("simulated insert failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_insert_table", fail_on_tasks)
    with pytest.raises(RuntimeError, match="simulated insert failure"):
        module.run_migration(
            source_path=source_database,
            target_url=postgres_database,
            mode="apply",
        )
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        for table in ("people", "accounts", "projects", "project_members", "tasks"):
            assert connection.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))).fetchone()[0] == 0


def test_setup_status_is_initialized_after_apply(
    source_database: Path,
    postgres_database: str,
):
    module = _load_module()
    module.run_migration(source_path=source_database, target_url=postgres_database, mode="apply")
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": postgres_database})
    code = (
        "from fastapi.testclient import TestClient; "
        "from app.main import app; "
        "response=TestClient(app).get('/api/setup/status'); "
        "assert response.status_code == 200, response.text; "
        "assert response.json()['initialized'] is True, response.json(); "
        "print('setup initialized')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, _output(result)
    assert "setup initialized" in result.stdout


def test_source_inventory_reports_orphans_and_unique_conflicts_without_sensitive_values(tmp_path: Path):
    module = _load_module()
    source = _build_source_database(tmp_path / "invalid-source.db")
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE accounts SET person_id=999 WHERE id=20")
        connection.execute("DROP INDEX ix_accounts_username")
        connection.execute(
            "INSERT INTO accounts (id, username, password_hash, person_id, status, is_tech_admin, "
            "must_change_password, created_at, updated_at) VALUES (21, 'migration-admin', "
            "'second-private-hash', NULL, 'active', 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()
    with module.open_source_readonly(source) as connection:
        audit = module.audit_source(connection, source)
    assert audit["orphan_foreign_keys"]
    assert audit["unique_conflicts"]
    payload = json.dumps(audit)
    assert "fixture-password-hash-secret" not in payload
    assert "second-private-hash" not in payload



def test_project_profile_migration_declares_only_current_columns():
    migration_path = (
        BACKEND_ROOT / "migrations" / "versions" /
        f"{PROJECT_PROFILE_REVISION}_restore_current_project_profile_columns.py"
    )
    assert migration_path.is_file()
    content = migration_path.read_text(encoding="utf-8")
    assert f'revision = "{PROJECT_PROFILE_REVISION}"' in content
    assert f'down_revision = "{PROJECT_PROFILE_DOWN_REVISION}"' in content
    for column in PROJECT_PROFILE_COLUMNS:
        assert f'"{column}"' in content
    for legacy in ARCHIVE_ONLY_COLUMNS | {"update_submissions.ceo_decision_required"}:
        assert legacy.split(".", 1)[1] not in content
    assert "drop_table" not in content


def test_operator_documentation_records_explicit_legacy_dispositions_and_downgrade_risk():
    content = DOCUMENT_PATH.read_text(encoding="utf-8")
    for column in PROJECT_PROFILE_COLUMNS | ARCHIVE_ONLY_COLUMNS:
        assert column in content
    assert "ceo_decision_required" in content
    assert "derived_and_verified" in content
    assert "???? downgrade" in content
    assert "???? profile ????" in content


def test_migration_module_has_exact_legacy_column_allowlists():
    module = _load_module()
    assert set(module.ARCHIVE_ONLY_COLUMNS) == ARCHIVE_ONLY_COLUMNS
    assert set(module.DERIVED_CANONICAL_COLUMNS) == {
        "update_submissions.ceo_decision_required"
    }
    assert not hasattr(module, "IGNORE_ALL_SOURCE_ONLY")
    assert not hasattr(module, "ALLOW_UNKNOWN_COLUMNS")


def test_archive_only_and_derived_columns_are_audited_without_raw_values(
    source_database: Path,
    postgres_database: str,
):
    module = _load_module()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="dry-run",
    )
    archive = {entry["field"]: entry for entry in report["archive_only_columns"]}
    assert set(archive) == ARCHIVE_ONLY_COLUMNS
    assert all(entry["nonempty_rows"] == 1 for entry in archive.values())
    assert all(entry["disposition"] == "archive_only" for entry in archive.values())
    derived = report["derived_canonical_columns"]
    assert derived == [{
        "field": "update_submissions.ceo_decision_required",
        "disposition": "derived_and_verified",
        "verified_rows": 1,
        "mismatch_count": 0,
    }]
    payload = json.dumps(report, ensure_ascii=False)
    for raw_value in ("FIXTURE-001", "Legacy Admin Title", "pending_owner"):
        assert raw_value not in payload
    assert report["apply_allowed"] is True
    assert report["blocking_errors"] == []


def test_apply_migrates_project_profile_fields_but_not_legacy_columns(
    source_database: Path,
    postgres_database: str,
):
    module = _load_module()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="apply",
    )
    assert report["applied"] is True
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        project = connection.execute(
            "SELECT project_type, client_name, background, objectives, expected_outcomes, "
            "lifecycle_status, kickoff_date, kickoff_by, initiated_by FROM projects WHERE id=30"
        ).fetchone()
        assert project == (
            "internal", "Fixture Client", "Fixture Background", "Fixture Objectives",
            "Fixture Outcomes", "active", "2026-01-02", "Fixture Kickoff",
            "Fixture Initiator",
        )
        columns = {
            (row[0], row[1])
            for row in connection.execute(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public'"
            )
        }
    for legacy in ARCHIVE_ONLY_COLUMNS | {"update_submissions.ceo_decision_required"}:
        assert tuple(legacy.split(".", 1)) not in columns


def test_ceo_derived_mismatch_blocks_dry_run_and_apply_without_writes(
    source_database: Path,
    postgres_database: str,
):
    with sqlite3.connect(source_database) as connection:
        connection.execute(
            "UPDATE update_submissions SET ceo_decision_required=1, "
            "human_result_json='{\"task_reports\":[{\"confirmation_status\":\"confirmed\"}]}'"
        )
        connection.commit()
    module = _load_module()
    report = module.run_migration(
        source_path=source_database,
        target_url=postgres_database,
        mode="dry-run",
    )
    assert report["apply_allowed"] is False
    assert report["derived_canonical_columns"][0]["verified_rows"] == 1
    assert report["derived_canonical_columns"][0]["mismatch_count"] == 1
    assert any("ceo_decision_required" in error for error in report["blocking_errors"])
    with pytest.raises(module.MigrationError, match="Apply refused"):
        module.run_migration(
            source_path=source_database,
            target_url=postgres_database,
            mode="apply",
        )
    with psycopg.connect(_psycopg_url(postgres_database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def _insert_lifecycle_backfill_rows(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        path = Path(database_url.removeprefix("sqlite:///"))
        with sqlite3.connect(path) as connection:
            connection.executemany(
                "INSERT INTO projects (id,name,status,is_active) VALUES (?,?,?,?)",
                [(901, "Status Wins", "ended", 1), (902, "Active Fallback", "", 1),
                 (903, "Archived Fallback", "", 0)],
            )
            connection.commit()
    else:
        with psycopg.connect(_psycopg_url(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO projects (id,name,status,is_active) VALUES (%s,%s,%s,%s)",
                    [(901, "Status Wins", "ended", True),
                     (902, "Active Fallback", "", True),
                     (903, "Archived Fallback", "", False)],
                )
            connection.commit()


def _assert_lifecycle_backfill(database_url: str) -> None:
    expected = [(901, "ended", True, "ended"), (902, "", True, "active"),
                (903, "", False, "archived")]
    if database_url.startswith("sqlite"):
        path = Path(database_url.removeprefix("sqlite:///"))
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT id,status,is_active,lifecycle_status FROM projects WHERE id>=901 ORDER BY id"
            ).fetchall()
        assert [(r[0], r[1], bool(r[2]), r[3]) for r in rows] == expected
    else:
        with psycopg.connect(_psycopg_url(database_url)) as connection:
            rows = connection.execute(
                "SELECT id,status,is_active,lifecycle_status FROM projects WHERE id>=901 ORDER BY id"
            ).fetchall()
        assert rows == expected


def _column_names(database_url: str, table: str) -> set[str]:
    if database_url.startswith("sqlite"):
        path = Path(database_url.removeprefix("sqlite:///"))
        with sqlite3.connect(path) as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    with psycopg.connect(_psycopg_url(database_url)) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s",
                (table,),
            )
        }


def _assert_profile_migration_round_trip(database_url: str) -> None:
    downgrade = _run_alembic(database_url, "downgrade", PROJECT_PROFILE_DOWN_REVISION)
    assert downgrade.returncode == 0, _output(downgrade)
    baseline_columns = _column_names(database_url, "projects")
    assert not (PROJECT_PROFILE_COLUMNS & baseline_columns)
    _insert_lifecycle_backfill_rows(database_url)
    upgrade = _run_alembic(database_url, "upgrade", "head")
    assert upgrade.returncode == 0, _output(upgrade)
    assert PROJECT_PROFILE_COLUMNS <= _column_names(database_url, "projects")
    _assert_lifecycle_backfill(database_url)
    downgrade = _run_alembic(database_url, "downgrade", PROJECT_PROFILE_DOWN_REVISION)
    assert downgrade.returncode == 0, _output(downgrade)
    assert _column_names(database_url, "projects") == baseline_columns
    upgrade = _run_alembic(database_url, "upgrade", "head")
    assert upgrade.returncode == 0, _output(upgrade)


def test_project_profile_migration_round_trip_sqlite(tmp_path: Path):
    database_url = _sqlite_url(tmp_path / "project-profile-round-trip.db")
    initial = _run_alembic(database_url, "upgrade", "head")
    assert initial.returncode == 0, _output(initial)
    _assert_profile_migration_round_trip(database_url)


def test_project_profile_migration_round_trip_postgresql(postgres_database: str):
    _assert_profile_migration_round_trip(postgres_database)
