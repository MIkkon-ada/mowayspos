from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXACT_MIGRATION = "I_UNDERSTAND_THIS_CHANGES_PROTECTED_DATA"
SAFETY_ENV_KEYS = (
    "DATABASE_URL",
    "APP_ENV",
    "PROTECTED_DATABASE_PATHS",
    "ALLOW_PROTECTED_DATABASE_MIGRATION",
)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _protected_path() -> Path:
    raw = os.environ["PROTECTED_DATABASE_PATHS"]
    separator = ";" if os.name == "nt" else os.pathsep
    return Path(raw.split(separator)[0]).resolve()


def _run_alembic(
    *,
    env: dict[str, str] | None = None,
    args: tuple[str, ...] = ("current",),
) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        child_env.pop(key, None)
    child_env["PYTHONPATH"] = str(BACKEND_ROOT)
    child_env.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def test_t7_alembic_without_database_url_fails_before_connect():
    result = _run_alembic()
    assert result.returncode != 0
    assert "DATABASE_URL must be explicitly configured." in _output(result)
    assert "Refusing to use a repository database fallback." in _output(result)


def test_t8_alembic_rejects_protected_database_without_authorization():
    protected = _protected_path()
    result = _run_alembic(
        env={
            "APP_ENV": "development",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
        }
    )
    assert result.returncode != 0
    assert "protected database migration is not authorized" in _output(result).lower()


def test_t9_alembic_rejects_truthy_but_inexact_authorization():
    protected = _protected_path()
    result = _run_alembic(
        env={
            "APP_ENV": "development",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
            "ALLOW_PROTECTED_DATABASE_MIGRATION": "true",
        }
    )
    assert result.returncode != 0
    assert "protected database migration is not authorized" in _output(result).lower()


def test_protected_migration_exact_authorization_logs_warning_before_connect(tmp_path: Path):
    protected = tmp_path / "authorized-protected.db"
    result = _run_alembic(
        env={
            "APP_ENV": "development",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
            "ALLOW_PROTECTED_DATABASE_MIGRATION": EXACT_MIGRATION,
        }
    )
    output = _output(result)
    assert "WARNING: protected database migration explicitly authorized" in output
    assert "DATABASE TARGET" in output
    assert str(protected.resolve()) in output


def test_t10_test_environment_rejects_exact_protected_authorization():
    protected = _protected_path()
    result = _run_alembic(
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
            "ALLOW_PROTECTED_DATABASE_MIGRATION": EXACT_MIGRATION,
        }
    )
    assert result.returncode != 0
    assert "test environment" in _output(result).lower()


def test_t11_temp_alembic_target_is_printed_before_online_connection(tmp_path: Path):
    database = tmp_path / "alembic-runtime.db"
    result = _run_alembic(
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "PROTECTED_DATABASE_PATHS": str(_protected_path()),
        }
    )
    output = _output(result)
    assert "DATABASE TARGET" in output
    assert "type: sqlite" in output.lower()
    assert str(database.resolve()) in output
    assert "protected: false" in output.lower()
    assert "mode: online" in output.lower()


def test_offline_migration_target_is_printed_before_work(tmp_path: Path):
    database = tmp_path / "offline-runtime.db"
    result = _run_alembic(
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "PROTECTED_DATABASE_PATHS": str(_protected_path()),
        },
        args=("upgrade", "head", "--sql"),
    )
    output = _output(result)
    assert "DATABASE TARGET" in output
    assert "mode: offline" in output.lower()


def test_alembic_environment_does_not_import_database_engine_module():
    env_file = BACKEND_ROOT / "migrations" / "env.py"
    code = (
        "from pathlib import Path; "
        "source=Path(r'" + str(env_file) + "').read_text(encoding='utf-8'); "
        "assert 'from app.database import' not in source; "
        "safety=source.index('app.database_safety'); "
        "models=source.index('app.models'); "
        "engine=source.index('connectable = engine_from_config'); "
        "assert safety < models; assert safety < engine"
    )
    child_env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        child_env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, _output(result)
