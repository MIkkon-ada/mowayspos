#!/usr/bin/env python
"""Controlled one-time SQLite to PostgreSQL data migration utility.

The source is always opened through SQLite's ``mode=ro`` URI.  The target URL
is accepted only from ``DATABASE_URL`` and is never rendered with credentials.
Dry-run performs inspection only.  Apply requires an empty, already-migrated
PostgreSQL database and imports all rows in one transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine, URL, make_url
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Time,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"
EXCLUDED_TABLES = {
    "auth_sessions": "environment-specific authentication sessions are not portable",
    "login_attempts": "environment-specific login security history is not portable",
}
ARCHIVE_ONLY_COLUMNS: dict[str, str] = {
    "achievements.is_desensitized": "retired desensitization flag retained only in the audited SQLite backup",
    "issues.feedback_required": "retired feedback flag retained only in the audited SQLite backup",
    "people.employee_code": "retired employee identifier is not mapped to username",
    "people.permission_scope": "retired scope does not re-enter the current RBAC model",
    "people.title": "retired title does not overwrite the current role field",
    "update_submissions.workflow_status": "retired workflow snapshot is superseded by current confirmation facts",
}
DERIVED_CANONICAL_COLUMNS: dict[str, str] = {
    "update_submissions.ceo_decision_required": (
        "derived from task_reports confirmation_status=pending_ceo_decision"
    ),
}
SENSITIVE_FIELD_MARKERS = (
    "password_hash",
    "session_token_hash",
    "api_key",
    "cookie",
    "transcript_text",
    "ai_result_json",
    "human_result_json",
    "ip_address",
)

# Some legacy columns are intentionally not declared as SQLite foreign keys.
# They still carry identity relationships and must be audited before migration.
LOGICAL_REFERENCES: dict[str, dict[str, tuple[str, str]]] = {
    "accounts": {"person_id": ("people", "id")},
    "project_members": {
        "project_id": ("projects", "id"),
        "person_id": ("people", "id"),
    },
    "tasks": {
        "project_id": ("projects", "id"),
        "owner_id": ("people", "id"),
        "owner_person_id": ("people", "id"),
        "coordinator_person_id": ("people", "id"),
    },
    "subtasks": {
        "task_id": ("tasks", "id"),
        "assignee_id": ("people", "id"),
    },
    "subtask_drafts": {
        "project_id": ("projects", "id"),
        "parent_task_id": ("tasks", "id"),
        "assignee_id": ("people", "id"),
    },
    "update_submissions": {
        "project_id": ("projects", "id"),
        "related_task_id": ("tasks", "id"),
        "related_subtask_id": ("subtasks", "id"),
        "submitter_id": ("people", "id"),
        "submitter_person_id": ("people", "id"),
        "target_owner_person_id": ("people", "id"),
        "current_handler_person_id": ("people", "id"),
        "confirmed_by_person_id": ("people", "id"),
        "parent_submission_id": ("update_submissions", "id"),
    },
    "meetings": {"project_id": ("projects", "id")},
    "achievements": {
        "project_id": ("projects", "id"),
        "related_task_id": ("tasks", "id"),
        "related_subtask_id": ("subtasks", "id"),
        "owner_id": ("people", "id"),
        "owner_person_id": ("people", "id"),
        "approved_by_person_id": ("people", "id"),
    },
    "achievement_submissions": {
        "project_id": ("projects", "id"),
        "related_task_id": ("tasks", "id"),
        "related_subtask_id": ("subtasks", "id"),
        "submitter_id": ("people", "id"),
    },
    "issues": {
        "project_id": ("projects", "id"),
        "related_task_id": ("tasks", "id"),
        "related_subtask_id": ("subtasks", "id"),
        "owner_id": ("people", "id"),
        "owner_person_id": ("people", "id"),
        "helper_person_id": ("people", "id"),
        "need_decision_by_person_id": ("people", "id"),
    },
    "project_close_requests": {
        "project_id": ("projects", "id"),
        "requester_person_id": ("people", "id"),
        "reviewer_person_id": ("people", "id"),
    },
    "member_change_requests": {
        "project_id": ("projects", "id"),
        "requester_person_id": ("people", "id"),
        "target_person_id": ("people", "id"),
        "reviewer_person_id": ("people", "id"),
    },
    "notifications": {
        "project_id": ("projects", "id"),
        "recipient_id": ("people", "id"),
    },
    "operation_logs": {
        "project_id": ("projects", "id"),
        "operator_person_id": ("people", "id"),
    },
}
KNOWN_UNIQUE_KEYS = {
    "accounts": (("username",),),
    "projects": (("name",),),
    "project_members": (("project_id", "person_id", "role"),),
}


class MigrationError(RuntimeError):
    """Fail-closed migration validation error."""


@dataclass(frozen=True)
class MigrationPlan:
    order: tuple[str, ...]
    columns: Mapping[str, tuple[str, ...]]
    target_metadata: MetaData


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate an empty PostgreSQL database from a read-only SQLite source."
    )
    parser.add_argument("--source-sqlite", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--report-json", type=Path)
    return parser


def validate_source_path(source_path: Path) -> Path:
    if not source_path.is_absolute():
        raise MigrationError("SQLite source path must be absolute.")
    resolved = source_path.resolve(strict=False)
    if not resolved.is_file():
        raise MigrationError("SQLite source file does not exist.")
    try:
        with resolved.open("rb") as stream:
            header = stream.read(16)
    except OSError as exc:
        raise MigrationError(f"Cannot read SQLite source: {exc}") from exc
    if header != b"SQLite format 3\x00":
        raise MigrationError("Source is not a SQLite database.")
    return resolved


@contextmanager
def open_source_readonly(source_path: Path) -> Iterator[sqlite3.Connection]:
    source = validate_source_path(source_path)
    uri = f"{source.as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise MigrationError(f"Cannot open SQLite source read-only: {exc}") from exc
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()


def validate_target_url(target_url: str) -> URL:
    if not target_url or not target_url.strip():
        raise MigrationError("DATABASE_URL is required for the PostgreSQL target.")
    try:
        url = make_url(target_url.strip())
    except Exception as exc:
        raise MigrationError("DATABASE_URL is not a valid database URL.") from exc
    if not url.drivername.startswith("postgresql"):
        raise MigrationError("Target DATABASE_URL must use PostgreSQL.")
    if not url.host or not url.database:
        raise MigrationError("PostgreSQL target must include host and database name.")
    return url


def safe_target_description(target_url: str) -> str:
    url = validate_target_url(target_url)
    port = f":{url.port}" if url.port is not None else ""
    return f"postgresql://{url.host}{port}/{url.database}"


def _quote_sqlite(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _sqlite_table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _sqlite_columns(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [
        {
            "name": row[1],
            "type": row[2],
            "nullable": not bool(row[3]),
            "default": row[4],
            "primary_key_order": row[5],
        }
        for row in connection.execute(f"PRAGMA table_info({_quote_sqlite(table)})")
    ]


def _sqlite_foreign_keys(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [
        {"column": row[3], "target_table": row[2], "target_column": row[4]}
        for row in connection.execute(f"PRAGMA foreign_key_list({_quote_sqlite(table)})")
    ]


def _known_unique_conflicts(
    connection: sqlite3.Connection,
    tables: set[str],
    table_columns: Mapping[str, set[str]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for table, keys in KNOWN_UNIQUE_KEYS.items():
        if table not in tables:
            continue
        for key in keys:
            if not set(key).issubset(table_columns[table]):
                continue
            rendered = ", ".join(_quote_sqlite(column) for column in key)
            groups = connection.execute(
                f"SELECT COUNT(*) FROM (SELECT {rendered} FROM {_quote_sqlite(table)} "
                f"GROUP BY {rendered} HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            if groups:
                conflicts.append({"table": table, "columns": list(key), "groups": groups})
    return conflicts


def _orphan_references(
    connection: sqlite3.Connection,
    tables: set[str],
    table_columns: Mapping[str, set[str]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    relationships: dict[str, dict[str, tuple[str, str]]] = {
        table: dict(mapping) for table, mapping in LOGICAL_REFERENCES.items()
    }
    for table in tables:
        for fk in _sqlite_foreign_keys(connection, table):
            relationships.setdefault(table, {})[fk["column"]] = (
                fk["target_table"], fk["target_column"]
            )
    for table, mapping in relationships.items():
        if table not in tables:
            continue
        for column, (parent, parent_column) in mapping.items():
            signature = (table, column, parent, parent_column)
            if signature in seen:
                continue
            seen.add(signature)
            if (
                column not in table_columns[table]
                or parent not in tables
                or parent_column not in table_columns[parent]
            ):
                continue
            count = connection.execute(
                f"SELECT COUNT(*) FROM {_quote_sqlite(table)} child "
                f"LEFT JOIN {_quote_sqlite(parent)} parent "
                f"ON parent.{_quote_sqlite(parent_column)} = child.{_quote_sqlite(column)} "
                f"WHERE child.{_quote_sqlite(column)} IS NOT NULL "
                f"AND parent.{_quote_sqlite(parent_column)} IS NULL"
            ).fetchone()[0]
            if count:
                errors.append(
                    {
                        "table": table,
                        "column": column,
                        "target_table": parent,
                        "target_column": parent_column,
                        "count": count,
                    }
                )
    return errors


def audit_source(connection: sqlite3.Connection, source_path: Path) -> dict[str, Any]:
    integrity_rows = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    integrity = "ok" if integrity_rows == ["ok"] else "; ".join(integrity_rows)
    tables = _sqlite_table_names(connection)
    table_set = set(tables)
    table_columns = {
        table: {entry["name"] for entry in _sqlite_columns(connection, table)}
        for table in tables
    }
    counts = {
        table: connection.execute(
            f"SELECT COUNT(*) FROM {_quote_sqlite(table)}"
        ).fetchone()[0]
        for table in tables
    }
    revision = None
    if "alembic_version" in table_set:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        if len(rows) == 1:
            revision = rows[0][0]
    orphans = _orphan_references(connection, table_set, table_columns)
    unique_conflicts = _known_unique_conflicts(connection, table_set, table_columns)
    nonpositive_ids: list[dict[str, Any]] = []
    schema: dict[str, Any] = {}
    for table in tables:
        columns = _sqlite_columns(connection, table)
        for column in columns:
            if column["primary_key_order"] and "INT" in (column["type"] or "").upper():
                count = connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_sqlite(table)} "
                    f"WHERE {_quote_sqlite(column['name'])} <= 0"
                ).fetchone()[0]
                if count:
                    nonpositive_ids.append(
                        {"table": table, "column": column["name"], "count": count}
                    )
        schema[table] = {
            "columns": columns,
            "foreign_keys": _sqlite_foreign_keys(connection, table),
        }
    return {
        "path": str(source_path.resolve()),
        "size": source_path.stat().st_size,
        "sha256": _sha256(source_path),
        "integrity_check": integrity,
        "alembic_revision": revision,
        "tables": tables,
        "table_counts": counts,
        "schema": schema,
        "orphan_foreign_keys": orphans,
        "unique_conflicts": unique_conflicts,
        "nonpositive_ids": nonpositive_ids,
    }


def current_alembic_head() -> str:
    config = Config(str(ALEMBIC_CONFIG))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise MigrationError(f"Expected one Alembic head, found {len(heads)}.")
    return heads[0]


def _load_orm_metadata() -> MetaData:
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.models import Base

    return Base.metadata


def convert_value(value: Any, column_type: Any, *, table: str, column: str) -> Any:
    if value is None:
        return None
    location = f"{table}.{column}"
    try:
        if isinstance(column_type, Boolean):
            if isinstance(value, bool):
                return value
            if value in (0, 1):
                return bool(value)
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1"}:
                    return True
                if lowered in {"false", "0"}:
                    return False
            raise ValueError("expected SQLite boolean 0/1 or true/false")
        if isinstance(column_type, DateTime):
            if isinstance(value, datetime):
                return value
            if not isinstance(value, str) or not value:
                raise ValueError("expected ISO datetime text")
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(column_type, Date):
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if not isinstance(value, str) or not value:
                raise ValueError("expected ISO date text")
            return date.fromisoformat(value)
        if isinstance(column_type, Time):
            if isinstance(value, time):
                return value
            if not isinstance(value, str) or not value:
                raise ValueError("expected ISO time text")
            return time.fromisoformat(value)
        if isinstance(column_type, JSON):
            if isinstance(value, str):
                return json.loads(value)
            if isinstance(value, (dict, list, int, float, bool)):
                return value
            raise ValueError("expected JSON text or JSON-compatible value")
        if isinstance(column_type, (Integer, SmallInteger, BigInteger)):
            if isinstance(value, bool):
                raise ValueError("boolean is not an integer ID")
            return int(value)
        if isinstance(column_type, (Float, Numeric)):
            if isinstance(column_type, Numeric):
                return Decimal(str(value))
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError("non-finite numeric value")
            return converted
        if isinstance(column_type, LargeBinary):
            if isinstance(value, bytes):
                return value
            raise ValueError("expected bytes")
        if isinstance(column_type, String):
            if not isinstance(value, str):
                return str(value)
            return value
        return value
    except (ValueError, TypeError, json.JSONDecodeError, InvalidOperation) as exc:
        raise MigrationError(f"Invalid value for {location}: {exc}") from exc


def analyze_column_mapping(
    target_table: Table,
    *,
    source_columns: set[str],
    source_row_count: int,
    source_nonempty_counts: Mapping[str, int],
    allowed_source_only: set[str] | None = None,
) -> dict[str, Any]:
    target_columns = {column.name: column for column in target_table.columns}
    allowed_source_only = allowed_source_only or set()
    shared = [column.name for column in target_table.columns if column.name in source_columns]
    source_only = []
    target_only = []
    blocking: list[str] = []
    for column in sorted(source_columns - set(target_columns)):
        count = int(source_nonempty_counts.get(column, 0))
        source_only.append({"column": column, "nonempty_rows": count})
        if count and column not in allowed_source_only:
            blocking.append(
                f"source-only column contains data: {target_table.name}.{column} ({count} rows)"
            )
    for name in sorted(set(target_columns) - source_columns):
        column = target_columns[name]
        has_default = column.server_default is not None or column.default is not None
        safe_missing = bool(column.nullable or has_default)
        target_only.append(
            {
                "column": name,
                "nullable": bool(column.nullable),
                "has_default": has_default,
                "safe_missing": safe_missing,
            }
        )
        if source_row_count and not safe_missing:
            blocking.append(
                f"required target column missing from source: {target_table.name}.{name}"
            )
    return {
        "insert_columns": shared,
        "source_only": source_only,
        "target_only": target_only,
        "blocking_errors": blocking,
    }


def topological_order(dependencies: Mapping[str, set[str]]) -> list[str]:
    remaining = {name: set(parents) for name, parents in dependencies.items()}
    unknown = {
        parent
        for parents in remaining.values()
        for parent in parents
        if parent not in remaining
    }
    if unknown:
        raise MigrationError(f"Unknown migration dependencies: {', '.join(sorted(unknown))}")
    order: list[str] = []
    while remaining:
        ready = sorted(name for name, parents in remaining.items() if not parents)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise MigrationError(f"Foreign-key dependency cycle detected: {cycle}")
        order.extend(ready)
        for name in ready:
            remaining.pop(name)
        for parents in remaining.values():
            parents.difference_update(ready)
    return order


def _reflect_target(connection: Connection) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=connection)
    return metadata


def _target_revision(connection: Connection) -> str | None:
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        return None
    rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def _target_table_counts(connection: Connection, metadata: MetaData) -> dict[str, int]:
    return {
        name: connection.execute(
            text(f'SELECT COUNT(*) FROM "{name.replace(chr(34), chr(34) * 2)}"')
        ).scalar_one()
        for name in sorted(metadata.tables)
        if name != "alembic_version"
    }


def _source_nonempty_counts(
    connection: sqlite3.Connection, table: str, columns: set[str]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for column in columns:
        counts[column] = connection.execute(
            f"SELECT COUNT(*) FROM {_quote_sqlite(table)} "
            f"WHERE {_quote_sqlite(column)} IS NOT NULL "
            f"AND CAST({_quote_sqlite(column)} AS TEXT) <> ''"
        ).fetchone()[0]
    return counts


def _current_submission_result(human_result: Any, ai_result: Any) -> dict[str, Any] | None:
    for raw in (human_result, ai_result):
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
        return None
    return {}


def _strict_legacy_boolean(value: Any) -> bool:
    if value is True or value == 1 or (isinstance(value, str) and value.strip().lower() in {"1", "true"}):
        return True
    if value is False or value == 0 or (isinstance(value, str) and value.strip().lower() in {"0", "false"}):
        return False
    raise ValueError("legacy boolean is not an explicit true/false value")


def _audit_legacy_column_dispositions(
    source: sqlite3.Connection,
    source_audit: Mapping[str, Any],
    target_metadata: MetaData,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    archive_only: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    blocking: list[str] = []
    source_schema = source_audit["schema"]

    for field, reason in sorted(ARCHIVE_ONLY_COLUMNS.items()):
        table, column = field.split(".", 1)
        source_columns = {
            entry["name"] for entry in source_schema.get(table, {}).get("columns", [])
        }
        if column not in source_columns:
            continue
        target_table = target_metadata.tables.get(table)
        if target_table is not None and column in target_table.columns:
            blocking.append(f"archive-only field exists in target schema: {field}")
        nonempty = source.execute(
            f"SELECT COUNT(*) FROM {_quote_sqlite(table)} "
            f"WHERE {_quote_sqlite(column)} IS NOT NULL "
            f"AND CAST({_quote_sqlite(column)} AS TEXT) <> ''"
        ).fetchone()[0]
        archive_only.append({
            "field": field,
            "disposition": "archive_only",
            "nonempty_rows": int(nonempty),
            "reason": reason,
        })

    field = "update_submissions.ceo_decision_required"
    table, column = field.split(".", 1)
    source_columns = {
        entry["name"] for entry in source_schema.get(table, {}).get("columns", [])
    }
    if column in source_columns:
        target_table = target_metadata.tables.get(table)
        if target_table is not None and column in target_table.columns:
            blocking.append(f"derived-only field exists in target schema: {field}")
        mismatch_count = 0
        rows = source.execute(
            "SELECT ceo_decision_required, human_result_json, ai_result_json "
            "FROM update_submissions"
        ).fetchall()
        for legacy, human_result, ai_result in rows:
            try:
                legacy_required = _strict_legacy_boolean(legacy)
            except ValueError:
                mismatch_count += 1
                continue
            result = _current_submission_result(human_result, ai_result)
            if result is None:
                mismatch_count += 1
                continue
            reports = result.get("task_reports") or []
            if not isinstance(reports, list):
                mismatch_count += 1
                continue
            derived_required = any(
                isinstance(report, dict)
                and str(report.get("confirmation_status") or "").strip()
                == "pending_ceo_decision"
                for report in reports
            )
            if legacy_required != derived_required:
                mismatch_count += 1
        derived.append({
            "field": field,
            "disposition": "derived_and_verified",
            "verified_rows": len(rows),
            "mismatch_count": mismatch_count,
        })
        if mismatch_count:
            blocking.append(
                f"derived field verification mismatch: {field} ({mismatch_count} rows)"
            )
    return archive_only, derived, blocking


def _target_dependencies(metadata: MetaData, tables: set[str]) -> dict[str, set[str]]:
    dependencies: dict[str, set[str]] = {name: set() for name in tables}
    for name in tables:
        table = metadata.tables[name]
        for constraint in table.foreign_key_constraints:
            parent = constraint.referred_table.name
            if parent in tables and parent != name:
                dependencies[name].add(parent)
    # Preserve audited legacy relationships even when old migrations omitted a
    # database FK.  Only relationships that exist in both schemas participate.
    for name in tables:
        for column, (parent, _) in LOGICAL_REFERENCES.get(name, {}).items():
            if (
                parent in tables
                and column in metadata.tables[name].columns
                and parent != name
            ):
                dependencies[name].add(parent)
    return dependencies


def _orm_schema_differences(target_metadata: MetaData) -> dict[str, Any]:
    orm = _load_orm_metadata()
    target_tables = set(target_metadata.tables) - {"alembic_version"}
    orm_tables = set(orm.tables)
    result: dict[str, Any] = {
        "target_database_only_tables": sorted(target_tables - orm_tables),
        "orm_only_tables": sorted(orm_tables - target_tables),
        "columns": {},
    }
    for table in sorted(target_tables & orm_tables):
        target_columns = set(target_metadata.tables[table].columns.keys())
        orm_columns = set(orm.tables[table].columns.keys())
        if target_columns != orm_columns:
            result["columns"][table] = {
                "target_database_only": sorted(target_columns - orm_columns),
                "orm_only": sorted(orm_columns - target_columns),
            }
    return result


def _validate_source_values(
    source: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    target_table: Table,
) -> list[str]:
    errors: list[str] = []
    if not columns:
        return errors
    rendered = ", ".join(_quote_sqlite(column) for column in columns)
    cursor = source.execute(f"SELECT {rendered} FROM {_quote_sqlite(table)}")
    for row_index, row in enumerate(cursor, start=1):
        for column, value in zip(columns, row):
            try:
                convert_value(value, target_table.c[column].type, table=table, column=column)
            except MigrationError as exc:
                errors.append(f"{exc} (row {row_index})")
    return errors


def _build_report_and_plan(
    source: sqlite3.Connection,
    source_path: Path,
    target: Connection,
    *,
    mode: str,
) -> tuple[dict[str, Any], MigrationPlan]:
    source_audit = audit_source(source, source_path)
    target_metadata = _reflect_target(target)
    target_tables = set(target_metadata.tables) - {"alembic_version"}
    source_tables = set(source_audit["tables"]) - {"alembic_version"}
    excluded = {
        table: reason
        for table, reason in EXCLUDED_TABLES.items()
        if table in target_tables or table in source_tables
    }
    planned = (source_tables & target_tables) - set(excluded)
    target_only = sorted((target_tables - source_tables) - set(excluded))
    source_only_tables = sorted((source_tables - target_tables) - set(excluded))
    dependencies = _target_dependencies(target_metadata, planned)
    order = topological_order(dependencies)
    columns_by_table: dict[str, tuple[str, ...]] = {}
    schema_differences: dict[str, Any] = {
        "source_only_tables": source_only_tables,
        "target_only_tables": target_only,
        "columns": {},
        "orm_vs_target_head": _orm_schema_differences(target_metadata),
    }
    blocking: list[str] = []
    archive_only_columns, derived_canonical_columns, disposition_errors = (
        _audit_legacy_column_dispositions(source, source_audit, target_metadata)
    )
    blocking.extend(disposition_errors)
    if source_audit["integrity_check"] != "ok":
        blocking.append("source integrity_check is not ok")
    if source_audit["orphan_foreign_keys"]:
        blocking.append(
            f"source contains {len(source_audit['orphan_foreign_keys'])} orphan foreign-key relationships"
        )
    if source_audit["unique_conflicts"]:
        blocking.append(
            f"source contains {len(source_audit['unique_conflicts'])} unique-constraint conflicts"
        )
    if source_audit["nonpositive_ids"]:
        blocking.append("source contains non-positive integer primary keys")
    for table in source_only_tables:
        count = source_audit["table_counts"].get(table, 0)
        if count:
            blocking.append(f"source-only table contains data: {table} ({count} rows)")
    for table in order:
        source_columns = {
            column["name"] for column in source_audit["schema"][table]["columns"]
        }
        target_table = target_metadata.tables[table]
        source_nonempty = _source_nonempty_counts(source, table, source_columns)
        handled_source_only = {
            column
            for column in source_columns - set(target_table.columns.keys())
            if f"{table}.{column}" in ARCHIVE_ONLY_COLUMNS
            or f"{table}.{column}" in DERIVED_CANONICAL_COLUMNS
        }
        mapping = analyze_column_mapping(
            target_table,
            source_columns=source_columns,
            source_row_count=source_audit["table_counts"][table],
            source_nonempty_counts=source_nonempty,
            allowed_source_only=handled_source_only,
        )
        columns_by_table[table] = tuple(mapping["insert_columns"])
        if mapping["source_only"] or mapping["target_only"]:
            schema_differences["columns"][table] = {
                "source_only": mapping["source_only"],
                "target_only": mapping["target_only"],
            }
        blocking.extend(mapping["blocking_errors"])
        blocking.extend(
            _validate_source_values(
                source, table, mapping["insert_columns"], target_table
            )
        )
    expected_revision = current_alembic_head()
    actual_revision = _target_revision(target)
    if actual_revision != expected_revision:
        blocking.append(
            f"target Alembic revision must be {expected_revision}; found {actual_revision or '<missing>'}"
        )
    target_counts = _target_table_counts(target, target_metadata)
    business_rows = sum(target_counts.values())
    if business_rows:
        blocking.append(f"target business tables are not empty ({business_rows} rows)")
    report = {
        "mode": mode,
        "source": {
            "path": source_audit["path"],
            "size": source_audit["size"],
            "sha256": source_audit["sha256"],
            "integrity_check": source_audit["integrity_check"],
            "alembic_revision": source_audit["alembic_revision"],
            "table_counts": source_audit["table_counts"],
        },
        "target": {
            "expected_alembic_revision": expected_revision,
            "alembic_revision": actual_revision,
            "table_counts_before": target_counts,
            "business_rows_before": business_rows,
        },
        "current_business_tables": sorted(target_tables),
        "planned_tables": order,
        "migration_order": order,
        "excluded_tables": excluded,
        "archive_only_columns": archive_only_columns,
        "derived_canonical_columns": derived_canonical_columns,
        "schema_differences": schema_differences,
        "orphan_foreign_keys": source_audit["orphan_foreign_keys"],
        "unique_conflicts": source_audit["unique_conflicts"],
        "blocking_errors": sorted(set(blocking)),
        "estimated_rows": sum(source_audit["table_counts"][table] for table in order),
        "apply_allowed": not blocking,
        "applied": False,
        "verification": {},
    }
    return report, MigrationPlan(
        order=tuple(order),
        columns=columns_by_table,
        target_metadata=target_metadata,
    )


def _insert_table(
    target_connection: Connection,
    source_connection: sqlite3.Connection,
    table_name: str,
    columns: Sequence[str],
    target_table: Table,
) -> int:
    if not columns:
        return 0
    rendered = ", ".join(_quote_sqlite(column) for column in columns)
    cursor = source_connection.execute(
        f"SELECT {rendered} FROM {_quote_sqlite(table_name)}"
    )
    total = 0
    while True:
        rows = cursor.fetchmany(500)
        if not rows:
            break
        payload = []
        for row in rows:
            payload.append(
                {
                    column: convert_value(
                        value,
                        target_table.c[column].type,
                        table=table_name,
                        column=column,
                    )
                    for column, value in zip(columns, row)
                }
            )
        target_connection.execute(target_table.insert(), payload)
        total += len(payload)
    return total


def _reset_sequences(connection: Connection, metadata: MetaData) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table_name in sorted(metadata.tables):
        if table_name == "alembic_version":
            continue
        table = metadata.tables[table_name]
        integer_pks = [
            column
            for column in table.primary_key.columns
            if isinstance(column.type, (Integer, SmallInteger, BigInteger))
        ]
        if len(integer_pks) != 1:
            continue
        column = integer_pks[0]
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table_name, "column_name": column.name},
        ).scalar_one_or_none()
        if not sequence:
            continue
        maximum = connection.execute(
            text(
                f'SELECT MAX("{column.name.replace(chr(34), chr(34) * 2)}") '
                f'FROM "{table_name.replace(chr(34), chr(34) * 2)}"'
            )
        ).scalar_one()
        if maximum is None:
            connection.execute(
                text("SELECT setval(CAST(:sequence AS regclass), 1, false)"),
                {"sequence": sequence},
            )
            result[table_name] = {"sequence": sequence, "max_id": None, "is_called": False}
        else:
            connection.execute(
                text("SELECT setval(CAST(:sequence AS regclass), :maximum, true)"),
                {"sequence": sequence, "maximum": maximum},
            )
            result[table_name] = {
                "sequence": sequence,
                "max_id": maximum,
                "is_called": True,
            }
    return result


def _verify_after_apply(
    source: sqlite3.Connection,
    target: Connection,
    plan: MigrationPlan,
) -> dict[str, Any]:
    source_counts = {
        table: source.execute(
            f"SELECT COUNT(*) FROM {_quote_sqlite(table)}"
        ).fetchone()[0]
        for table in plan.order
    }
    target_counts = {
        table: target.execute(
            text(f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"')
        ).scalar_one()
        for table in plan.order
    }
    mismatches = {
        table: {"source": source_counts[table], "target": target_counts[table]}
        for table in plan.order
        if source_counts[table] != target_counts[table]
    }
    tech_admin = target.execute(
        text("SELECT COUNT(*) FROM accounts WHERE is_tech_admin = true")
    ).scalar_one()
    auth_sessions = target.execute(text("SELECT COUNT(*) FROM auth_sessions")).scalar_one()
    login_attempts = target.execute(text("SELECT COUNT(*) FROM login_attempts")).scalar_one()
    if mismatches:
        raise MigrationError(f"Post-apply row count mismatch in: {', '.join(mismatches)}")
    if tech_admin < 1:
        raise MigrationError("Post-apply verification found no technical administrator.")
    if auth_sessions or login_attempts:
        raise MigrationError("Excluded authentication security tables are not empty.")
    return {
        "row_counts_match": True,
        "row_counts": target_counts,
        "tech_admin_count": tech_admin,
        "auth_sessions": auth_sessions,
        "login_attempts": login_attempts,
    }


def _write_report(report: Mapping[str, Any], report_path: Path | None) -> None:
    if report_path is None:
        return
    destination = report_path.resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_migration(
    *,
    source_path: Path,
    target_url: str,
    mode: str,
    report_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"dry-run", "apply"}:
        raise MigrationError("Mode must be dry-run or apply.")
    source_path = validate_source_path(source_path)
    validate_target_url(target_url)
    engine: Engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with open_source_readonly(source_path) as source:
            if mode == "dry-run":
                with engine.connect() as target:
                    report, _ = _build_report_and_plan(
                        source, source_path, target, mode=mode
                    )
            else:
                with engine.begin() as target:
                    metadata = _reflect_target(target)
                    lock_tables = sorted(set(metadata.tables) - {"alembic_version"})
                    for table_name in lock_tables:
                        target.execute(
                            text(
                                f'LOCK TABLE "{table_name.replace(chr(34), chr(34) * 2)}" '
                                "IN ACCESS EXCLUSIVE MODE"
                            )
                        )
                    report, plan = _build_report_and_plan(
                        source, source_path, target, mode=mode
                    )
                    if not report["apply_allowed"]:
                        _write_report(report, report_path)
                        raise MigrationError(
                            "Apply refused: " + "; ".join(report["blocking_errors"])
                        )
                    inserted: dict[str, int] = {}
                    for table_name in plan.order:
                        inserted[table_name] = _insert_table(
                            target,
                            source,
                            table_name,
                            plan.columns[table_name],
                            plan.target_metadata.tables[table_name],
                        )
                    sequences = _reset_sequences(target, plan.target_metadata)
                    verification = _verify_after_apply(source, target, plan)
                    report["applied"] = True
                    report["inserted_rows"] = inserted
                    report["sequence_calibration"] = sequences
                    report["verification"] = verification
            _write_report(report, report_path)
            print(
                f"migration mode={mode} source_sha256={report['source']['sha256']} "
                f"apply_allowed={str(report['apply_allowed']).lower()} "
                f"estimated_rows={report['estimated_rows']}",
                flush=True,
            )
            if report["blocking_errors"]:
                print(f"blocking_errors={len(report['blocking_errors'])}", flush=True)
            return report
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    target_url = os.environ.get("DATABASE_URL", "")
    mode = "apply" if args.apply else "dry-run"
    try:
        report = run_migration(
            source_path=args.source_sqlite,
            target_url=target_url,
            mode=mode,
            report_path=args.report_json,
        )
    except MigrationError as exc:
        print(f"migration refused: {exc}", file=sys.stderr)
        return 2
    if mode == "dry-run" and not report["apply_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
