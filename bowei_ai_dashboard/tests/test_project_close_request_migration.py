from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

import app.database as app_database
from app import models as _models  # noqa: F401 - register all existing tables
from app.database import Base


OLD_HEAD = "4bf512ac2391"
NEW_REVISION = "a7d9c3e5f102"
ROOT = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    # migrations/env.py intentionally sources its URL from app.database instead
    # of the Alembic Config, so keep that process-level source pointed at the
    # per-test database before Alembic imports the migration environment.
    app_database.SQLALCHEMY_DATABASE_URL = url
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _prepare_old_head_database(path: Path) -> tuple[str, Config]:
    url = f"sqlite:///{path.as_posix()}"
    engine = sa.create_engine(url)
    old_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != "project_close_requests"
    ]
    Base.metadata.create_all(engine, tables=old_tables)
    cfg = _config(url)
    command.stamp(cfg, OLD_HEAD)
    return url, cfg


def test_migration_upgrade_creates_expected_table_columns_indexes_and_foreign_keys(tmp_path: Path):
    url, cfg = _prepare_old_head_database(tmp_path / "upgrade.db")
    command.upgrade(cfg, "head")

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
    url, cfg = _prepare_old_head_database(tmp_path / "roundtrip.db")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, OLD_HEAD)
    assert "project_close_requests" not in sa.inspect(sa.create_engine(url)).get_table_names()

    command.upgrade(cfg, "head")
    assert "project_close_requests" in sa.inspect(sa.create_engine(url)).get_table_names()


def test_migration_downgrade_refuses_when_close_request_data_exists(tmp_path: Path):
    url, cfg = _prepare_old_head_database(tmp_path / "protected-request.db")
    command.upgrade(cfg, "head")
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO projects (id,name,status,is_active) VALUES (1,'P','active',1)"))
        conn.execute(sa.text("""
            INSERT INTO project_close_requests (
                project_id, summary, objective_result, unfinished_items_json,
                remaining_risks_json, handover_plan, retrospective, status
            ) VALUES (1,'s','o','[]','[]','h','r','pending')
        """))

    with pytest.raises(RuntimeError, match="project_close_requests contains data"):
        command.downgrade(cfg, OLD_HEAD)


@pytest.mark.parametrize("status", ["pending_close", "ended"])
def test_migration_downgrade_refuses_when_projects_use_new_status(tmp_path: Path, status: str):
    url, cfg = _prepare_old_head_database(tmp_path / f"protected-{status}.db")
    command.upgrade(cfg, "head")
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO projects (id,name,status,is_active) VALUES (1,'P',:status,0)"),
            {"status": status},
        )

    with pytest.raises(RuntimeError, match="projects still use pending_close or ended"):
        command.downgrade(cfg, OLD_HEAD)
