from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine

from tests.test_migration_bootstrap import _output, _run_alembic


PRE_ISSUE_HELPER_ID_REVISION = "m4n5o6p7q8r9"
ISSUE_HELPER_ID_REVISION = "n5o6p7q8r9s0"


def test_issue_helper_identity_migration_backfills_only_unique_names_and_guards_downgrade(tmp_path: Path):
    database = tmp_path / "issue-helper-identity.db"
    result = _run_alembic(database, "upgrade", PRE_ISSUE_HELPER_ID_REVISION)
    assert result.returncode == 0, _output(result)

    engine = create_engine(f"sqlite:///{database.resolve().as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO people (id, name, system_role, is_active) VALUES "
                "(1, '唯一协助人', 'normal_member', 1), "
                "(2, '重名协助人', 'normal_member', 1), "
                "(3, '重名协助人', 'normal_member', 1)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO issues (id, description, helper) VALUES "
                "(1, '唯一姓名历史事项', '唯一协助人'), "
                "(2, '重名历史事项', '重名协助人')"
            )
        )

    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT id, helper_person_id FROM issues ORDER BY id")
        ).all() == [(1, 1), (2, None)]

    result = _run_alembic(database, "downgrade", PRE_ISSUE_HELPER_ID_REVISION)
    assert result.returncode != 0
    assert "issue helper identity data would be lost" in _output(result)

    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE issues SET helper_person_id = NULL"))
    result = _run_alembic(database, "downgrade", PRE_ISSUE_HELPER_ID_REVISION)
    assert result.returncode == 0, _output(result)
    engine.dispose()
