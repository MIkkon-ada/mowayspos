from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).resolve().parents[1]
AI_CONFIG_REVISION = "a6b7c8d9e0f1"
PREVIOUS_REVISION = "f5a6b7c8d9e0"


def _run(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
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


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def test_ai_capability_configuration_migration_round_trip(tmp_path: Path):
    database = tmp_path / "ai-capability-configuration.db"

    _assert_ok(_run(database, "upgrade", AI_CONFIG_REVISION))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert {
        "ai_models",
        "ai_model_credentials",
        "ai_capability_policies",
        "ai_invocation_logs",
    }.issubset(inspector.get_table_names())
    assert {constraint["name"] for constraint in inspector.get_unique_constraints("ai_models")} >= {
        "uq_ai_models_code"
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("ai_capability_policies")
    } >= {"uq_ai_capability_policies_key"}

    _assert_ok(_run(database, "downgrade", PREVIOUS_REVISION))
    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert {
        "ai_models",
        "ai_model_credentials",
        "ai_capability_policies",
        "ai_invocation_logs",
    }.isdisjoint(inspector.get_table_names())
