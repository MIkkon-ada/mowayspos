from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_REVISION = "7f3a2c9d8e41"
BASELINE_REVISION = "614f43813210"
PERSON_ID_REVISION = "d14986ccb2dd"
MARKER_TABLE = "_moways_migration_bootstrap"
MARKER_TOKEN = "POST_D149_PRE_4BF_BOOTSTRAP_V1"
DEV_CREATE_ALL_AUTHORIZATION = "I_UNDERSTAND_THIS_IS_DEV_ONLY"
D149_BUSINESS_TABLES = {
    "accounts",
    "achievement_submissions",
    "achievements",
    "auth_sessions",
    "issues",
    "login_attempts",
    "meetings",
    "member_change_requests",
    "notifications",
    "operation_logs",
    "people",
    "platform_settings",
    "project_members",
    "projects",
    "subtask_drafts",
    "subtasks",
    "tasks",
    "update_submissions",
}
RELATED_SUBTASK_TABLES = {
    "update_submissions": "ix_update_submissions_related_subtask_id",
    "achievements": "ix_achievements_related_subtask_id",
    "issues": "ix_issues_related_subtask_id",
}
SAFETY_ENV_KEYS = (
    "ALLOW_DEV_SCHEMA_CREATE_ALL",
    "ALLOW_PROTECTED_DATABASE_MIGRATION",
    "APP_ENV",
    "BOWEI_DEV_MODE",
    "DATABASE_URL",
    "PROTECTED_DATABASE_PATHS",
)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _current_head_revision() -> str:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(BACKEND_ROOT / "migrations"),
    )
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1
    return heads[0]


def _protected_path() -> Path:
    raw = os.environ["PROTECTED_DATABASE_PATHS"]
    separator = ";" if os.name == "nt" else os.pathsep
    return Path(raw.split(separator)[0]).resolve()


def _child_env(database_url: str, **updates: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        env.pop(key, None)
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": database_url,
            "PROTECTED_DATABASE_PATHS": str(_protected_path()),
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    env.update(updates)
    return env


def _run_alembic(
    database: Path,
    *args: str,
    database_url: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=_child_env(database_url or _sqlite_url(database)),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _run_python(
    database: Path,
    code: str,
    **env_updates: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=_child_env(_sqlite_url(database), **env_updates),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_names(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not row[0].startswith("sqlite_")
        }


def _revision(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    return str(row[0])


def _columns(database: Path, table: str) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
        }


def _index_names(database: Path, table: str) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            str(row[1])
            for row in connection.execute(f"PRAGMA index_list({_quote(table)})")
        }


def _foreign_keys(database: Path, table: str) -> set[tuple[str, str, str]]:
    with sqlite3.connect(database) as connection:
        return {
            (str(row[3]), str(row[2]), str(row[4]))
            for row in connection.execute(
                f"PRAGMA foreign_key_list({_quote(table)})"
            )
        }


def _schema_snapshot(database: Path) -> dict[str, object]:
    with sqlite3.connect(database) as connection:
        tables = sorted(_table_names(database) - {"alembic_version"})
        snapshot: dict[str, object] = {}
        for table in tables:
            quoted_table = _quote(table)
            columns = sorted(
                [
                {
                    "name": str(row[1]),
                    "type": str(row[2]).upper(),
                    "nullable": not bool(row[3]),
                    "default": row[4],
                    "primary_key": int(row[5]),
                }
                for row in connection.execute(
                    f"PRAGMA table_info({quoted_table})"
                )
                ],
                key=lambda item: str(item["name"]),
            )
            foreign_keys = sorted(
                {
                    (
                        str(row[3]),
                        str(row[2]),
                        str(row[4]),
                        str(row[5]),
                        str(row[6]),
                        str(row[7]),
                    )
                    for row in connection.execute(
                        f"PRAGMA foreign_key_list({quoted_table})"
                    )
                }
            )
            indexes: list[dict[str, object]] = []
            for row in connection.execute(f"PRAGMA index_list({quoted_table})"):
                index_name = str(row[1])
                quoted_index = _quote(index_name)
                indexes.append(
                    {
                        "name": index_name,
                        "unique": bool(row[2]),
                        "origin": str(row[3]),
                        "partial": bool(row[4]),
                        "columns": tuple(
                            str(item[2])
                            for item in connection.execute(
                                f"PRAGMA index_info({quoted_index})"
                            )
                        ),
                    }
                )
            snapshot[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": sorted(indexes, key=lambda item: str(item["name"])),
            }
    return snapshot


def _create_current_orm_database(
    database: Path,
    *,
    name_related_subtask_constraints: bool = False,
) -> None:
    constraint_setup = ""
    if name_related_subtask_constraints:
        constraint_setup = """
from app.database import Base
import app.models

constraint_names = {
    "update_submissions": "fk_upd_sub_related_subtask_id_subtasks",
    "achievements": "fk_achievements_related_subtask_id_subtasks",
    "issues": "fk_issues_related_subtask_id_subtasks",
}
for table_name, constraint_name in constraint_names.items():
    table = Base.metadata.tables[table_name]
    matches = [
        constraint
        for constraint in table.foreign_key_constraints
        if {element.parent.name for element in constraint.elements}
        == {"related_subtask_id"}
    ]
    assert len(matches) == 1
    matches[0].name = constraint_name
"""
    result = _run_python(
        database,
        constraint_setup + "\nfrom app.main import _startup\n_startup()",
        ALLOW_DEV_SCHEMA_CREATE_ALL=DEV_CREATE_ALL_AUTHORIZATION,
    )
    assert result.returncode == 0, _output(result)


def _current_orm_business_tables(database: Path) -> set[str]:
    _create_current_orm_database(database)
    return _table_names(database) - {"alembic_version"}


def _assert_related_subtask_fields(database: Path, *, present: bool) -> None:
    for table, index_name in RELATED_SUBTASK_TABLES.items():
        assert ("related_subtask_id" in _columns(database, table)) is present
        assert (index_name in _index_names(database, table)) is present
        assert (
            ("related_subtask_id", "subtasks", "id")
            in _foreign_keys(database, table)
        ) is present


def _load_d149_revision():
    path = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / "d14986ccb2dd_add_person_id_to_business_tables.py"
    )
    spec = importlib.util.spec_from_file_location("migration_d149_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t1_empty_database_upgrades_to_d149(tmp_path: Path):
    database = tmp_path / "upgrade-d149.db"

    result = _run_alembic(database, "upgrade", PERSON_ID_REVISION)

    assert result.returncode == 0, _output(result)
    assert _table_names(database) - {"alembic_version"} == D149_BUSINESS_TABLES
    assert MARKER_TABLE not in _table_names(database)
    assert _revision(database) == PERSON_ID_REVISION
    _assert_related_subtask_fields(database, present=False)


def test_t2_empty_database_upgrades_to_head(tmp_path: Path):
    database = tmp_path / "upgrade-head.db"
    orm = tmp_path / "current-orm-reference.db"
    current_head = _current_head_revision()
    expected_tables = _current_orm_business_tables(orm)

    result = _run_alembic(database, "upgrade", "head")

    assert result.returncode == 0, _output(result)
    assert _table_names(database) - {"alembic_version"} == expected_tables
    assert MARKER_TABLE not in _table_names(database)
    assert _revision(database) == current_head
    _assert_related_subtask_fields(database, present=True)


def test_t3_head_schema_matches_current_orm(tmp_path: Path):
    migrated = tmp_path / "migrated-head.db"
    orm = tmp_path / "current-orm.db"
    result = _run_alembic(migrated, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    _create_current_orm_database(orm)

    assert _revision(migrated) == _current_head_revision()
    assert _schema_snapshot(migrated) == _schema_snapshot(orm)


def test_t4_d149_schema_matches_current_orm_downgraded_from_head(tmp_path: Path):
    migrated = tmp_path / "migrated-d149.db"
    orm = tmp_path / "orm-d149.db"
    result = _run_alembic(migrated, "upgrade", PERSON_ID_REVISION)
    assert result.returncode == 0, _output(result)
    _create_current_orm_database(
        orm,
        name_related_subtask_constraints=True,
    )
    result = _run_alembic(orm, "stamp", _current_head_revision())
    assert result.returncode == 0, _output(result)
    result = _run_alembic(orm, "downgrade", PERSON_ID_REVISION)
    assert result.returncode == 0, _output(result)

    assert _schema_snapshot(migrated) == _schema_snapshot(orm)


def test_t5_invalid_marker_fails_closed_and_is_preserved(tmp_path: Path):
    database = tmp_path / "invalid-marker.db"
    result = _run_alembic(database, "upgrade", BASELINE_REVISION)
    assert result.returncode == 0, _output(result)
    assert MARKER_TABLE in _table_names(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE {_quote(MARKER_TABLE)} SET token = ? WHERE id = 1",
            ("WRONG_TOKEN",),
        )
        connection.commit()
    before = _schema_snapshot(database)

    result = _run_alembic(database, "upgrade", PERSON_ID_REVISION)

    assert result.returncode != 0
    assert "bootstrap marker" in _output(result).lower()
    assert _revision(database) == BASELINE_REVISION
    assert _schema_snapshot(database) == before
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            f"SELECT id, token FROM {_quote(MARKER_TABLE)}"
        ).fetchall()
    assert rows == [(1, "WRONG_TOKEN")]


def test_t6_missing_marker_uses_legacy_path_and_does_not_succeed(tmp_path: Path):
    database = tmp_path / "legacy-missing-schema.db"
    result = _run_alembic(database, "stamp", BASELINE_REVISION)
    assert result.returncode == 0, _output(result)

    result = _run_alembic(database, "upgrade", PERSON_ID_REVISION)

    assert result.returncode != 0
    assert "tasks" in _output(result).lower()
    assert _revision(database) == BASELINE_REVISION
    assert MARKER_TABLE not in _table_names(database)


def test_t7_current_head_database_upgrade_is_a_data_preserving_noop(
    tmp_path: Path,
):
    database = tmp_path / "current-head.db"
    current_head = _current_head_revision()
    _create_current_orm_database(database)
    result = _run_alembic(database, "stamp", current_head)
    assert result.returncode == 0, _output(result)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO platform_settings (id, data_json) VALUES (?, ?)",
            (99, '{"fingerprint":"keep"}'),
        )
        connection.commit()
    before = database.read_bytes()

    result = _run_alembic(database, "upgrade", "head")

    assert result.returncode == 0, _output(result)
    assert _revision(database) == current_head
    assert database.read_bytes() == before


def test_t8_downgrade_stops_at_d149_without_schema_changes(tmp_path: Path):
    database = tmp_path / "downgrade-boundary.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)

    result = _run_alembic(database, "downgrade", PERSON_ID_REVISION)
    assert result.returncode == 0, _output(result)
    assert _revision(database) == PERSON_ID_REVISION
    _assert_related_subtask_fields(database, present=False)
    before = _schema_snapshot(database)

    result = _run_alembic(database, "downgrade", BASELINE_REVISION)

    assert result.returncode != 0
    assert "downgrade below d14986ccb2dd is unsupported" in _output(result).lower()
    assert _revision(database) == PERSON_ID_REVISION
    assert _schema_snapshot(database) == before


def test_t9_default_startup_uses_migrated_schema_without_create_all_or_seed(
    tmp_path: Path,
):
    database = tmp_path / "startup.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    before = _schema_snapshot(database)
    code = """
import app.main as main

def forbidden(*args, **kwargs):
    raise AssertionError("create_all or seed must not run")

main.Base.metadata.create_all = forbidden
main.seed = forbidden
main._startup()
"""

    result = _run_python(database, code)

    assert result.returncode == 0, _output(result)
    assert _schema_snapshot(database) == before
    assert _revision(database) == _current_head_revision()


def test_migration_graph_has_one_current_head():
    assert _current_head_revision()


def test_marker_validation_uses_dialect_portable_primary_key_inspection(
    monkeypatch,
):
    revision = _load_d149_revision()

    class Inspector:
        def get_table_names(self):
            return [MARKER_TABLE]

        def get_columns(self, table_name):
            assert table_name == MARKER_TABLE
            return [
                {"name": "id", "type": revision.sa.Integer(), "nullable": False},
                {
                    "name": "token",
                    "type": revision.sa.String(length=100),
                    "nullable": False,
                },
            ]

        def get_pk_constraint(self, table_name):
            assert table_name == MARKER_TABLE
            return {"constrained_columns": ["id"]}

        def get_unique_constraints(self, table_name):
            assert table_name == MARKER_TABLE
            return [{"column_names": ["token"]}]

    class Bind:
        def execute(self, statement):
            return [(1, MARKER_TOKEN)]

    dropped: list[str] = []
    monkeypatch.setattr(revision.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(revision.sa, "inspect", lambda bind: Inspector())
    monkeypatch.setattr(revision.op, "drop_table", dropped.append)

    assert revision._consume_valid_bootstrap_marker() is True
    assert dropped == [MARKER_TABLE]


def test_postgresql_dialect_compiles_static_bootstrap_ddl(tmp_path: Path):
    database = tmp_path / "unused.db"
    result = _run_alembic(
        database,
        "upgrade",
        BOOTSTRAP_REVISION,
        "--sql",
        database_url="postgresql+psycopg://bootstrap:bootstrap@127.0.0.1/bootstrap",
    )

    assert result.returncode == 0, _output(result)
    output = _output(result).lower()
    assert "create table projects" in output
    assert "create table _moways_migration_bootstrap" in output
    assert "pragma" not in output
