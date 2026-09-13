from __future__ import annotations

import warnings
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy.exc import SAWarning

from app import models  # noqa: F401
from app.database import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_REVISION = "m4n5o6p7q8r"


def _migrate(database: Path, command: str, revision: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}", "PYTHONPATH": str(BACKEND_ROOT)})
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", command, revision],
        cwd=BACKEND_ROOT, env=env, capture_output=True, text=True, check=False,
    )


def test_metadata_has_no_meeting_document_source_foreign_key_cycle():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", SAWarning)
        Base.metadata.sorted_tables

    assert not any(
        "meeting_document_sources" in str(warning.message)
        and "meetings" in str(warning.message)
        for warning in captured
    )


def test_head_migration_removes_meeting_document_source_reverse_link(tmp_path: Path):
    database = tmp_path / "meeting-document-source.db"
    result = _migrate(database, "upgrade", MIGRATION_REVISION)

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(meeting_document_sources)")}
    assert "meeting_id" not in columns


def test_downgrade_backfills_reverse_link_from_lowest_meeting_id(tmp_path: Path):
    database = tmp_path / "meeting-document-source-roundtrip.db"
    result = _migrate(database, "upgrade", MIGRATION_REVISION)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database) as connection:
        connection.executemany(
            """
            INSERT INTO meeting_document_sources
                (id, project_id, original_name, storage_key, mime_type, size_bytes, content_hash)
            VALUES (?, 1, ?, ?, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 1, ?)
            """,
            [
                (101, "linked.docx", "meeting-source-linked", "hash-linked"),
                (102, "unlinked.docx", "meeting-source-unlinked", "hash-unlinked"),
            ],
        )
        connection.executemany(
            "INSERT INTO meetings (id, document_source_id) VALUES (?, 101)",
            [(9,), (3,)],
        )

    result = _migrate(database, "downgrade", "l3m4n5o6p7q")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        reverse_links = dict(connection.execute(
            "SELECT id, meeting_id FROM meeting_document_sources WHERE id IN (101, 102)"
        ))
    assert reverse_links == {101: 3, 102: None}

    result = _migrate(database, "upgrade", MIGRATION_REVISION)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(meeting_document_sources)")}
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert "meeting_id" not in columns
    assert integrity == "ok"
