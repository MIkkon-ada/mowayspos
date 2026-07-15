from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FAIL_CLOSED_TEXT = (
    "DATABASE_URL must be explicitly configured.",
    "Refusing to use a repository database fallback.",
)
EXACT_CREATE_ALL = "I_UNDERSTAND_THIS_IS_DEV_ONLY"
EXACT_MEMORY = "I_UNDERSTAND_THIS_IS_TEST_ONLY"
SAFETY_ENV_KEYS = (
    "DATABASE_URL",
    "APP_ENV",
    "PROTECTED_DATABASE_PATHS",
    "ALLOW_TEST_MEMORY_DATABASE",
    "ALLOW_DEV_SCHEMA_CREATE_ALL",
    "ALLOW_PROTECTED_DATABASE_MIGRATION",
    "BOWEI_DEV_MODE",
)


def _run_python(
    code: str,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    for key in SAFETY_ENV_KEYS:
        child_env.pop(key, None)
    child_env["PYTHONPATH"] = str(BACKEND_ROOT)
    child_env.update(env or {})
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _configured_protected_path() -> Path:
    raw = os.environ["PROTECTED_DATABASE_PATHS"]
    separator = ";" if os.name == "nt" else os.pathsep
    return Path(raw.split(separator)[0]).resolve()


def test_t1_missing_database_url_fails_closed_without_repository_file(tmp_path: Path):
    result = _run_python("import app.database", cwd=tmp_path)
    output = _output(result)

    assert result.returncode != 0
    assert all(message in output for message in FAIL_CLOSED_TEXT)
    assert not (BACKEND_ROOT / "bowei_ai_dashboard.db").exists()
    assert not (tmp_path / "bowei_ai_dashboard.db").exists()


def test_t2_empty_database_url_fails_closed(tmp_path: Path):
    result = _run_python("import app.database", cwd=tmp_path, env={"DATABASE_URL": ""})
    assert result.returncode != 0
    assert all(message in _output(result) for message in FAIL_CLOSED_TEXT)


def test_t3_whitespace_database_url_fails_closed(tmp_path: Path):
    result = _run_python("import app.database", cwd=tmp_path, env={"DATABASE_URL": "   "})
    assert result.returncode != 0
    assert all(message in _output(result) for message in FAIL_CLOSED_TEXT)


def test_placeholder_database_url_fails_closed(tmp_path: Path):
    result = _run_python(
        "from app.database_safety import require_database_url; require_database_url()",
        cwd=tmp_path,
        env={"DATABASE_URL": "sqlite:///D:/replace-with-absolute-path/runtime.db"},
    )
    assert result.returncode != 0
    assert "placeholder" in _output(result).lower()


def test_t4_relative_sqlite_path_is_rejected(tmp_path: Path):
    result = _run_python(
        "from app.database_safety import normalize_database_target; "
        "normalize_database_target('sqlite:///runtime.db')",
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "absolute" in _output(result).lower()


def test_t5_temp_absolute_sqlite_path_is_normalized(tmp_path: Path):
    database = tmp_path / "nested" / "runtime.db"
    result = _run_python(
        "import os; from app.database_safety import normalize_database_target, describe_database_target; "
        "target=normalize_database_target(os.environ['DATABASE_URL']); "
        "print(target.path); print(describe_database_target(os.environ['DATABASE_URL']))",
        cwd=tmp_path,
        env={"DATABASE_URL": _sqlite_url(database)},
    )
    assert result.returncode == 0, _output(result)
    assert str(database.resolve()) in result.stdout
    assert "type: sqlite" in result.stdout.lower()
    assert "protected: false" in result.stdout.lower()


def test_memory_database_requires_test_and_exact_opt_in(tmp_path: Path):
    code = (
        "from app.database_safety import normalize_database_target; "
        "print(normalize_database_target('sqlite:///:memory:').kind)"
    )
    rejected = _run_python(code, cwd=tmp_path, env={"APP_ENV": "test"})
    allowed = _run_python(
        code,
        cwd=tmp_path,
        env={"APP_ENV": "test", "ALLOW_TEST_MEMORY_DATABASE": EXACT_MEMORY},
    )
    production = _run_python(
        code,
        cwd=tmp_path,
        env={"APP_ENV": "production", "ALLOW_TEST_MEMORY_DATABASE": EXACT_MEMORY},
    )
    assert rejected.returncode != 0
    assert allowed.returncode == 0, _output(allowed)
    assert production.returncode != 0


def test_t6_test_environment_rejects_protected_database_before_connect(tmp_path: Path):
    protected = _configured_protected_path()
    result = _run_python(
        "import app.database",
        cwd=tmp_path,
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
        },
    )
    assert result.returncode != 0
    assert "test environment" in _output(result).lower()
    assert "protected" in _output(result).lower()


def test_protected_paths_compare_canonical_case_and_slashes(tmp_path: Path):
    protected = tmp_path / "Protected" / "runtime.db"
    alternate = str(protected).replace("\\", "/")
    if os.name == "nt":
        alternate = alternate.swapcase()
    result = _run_python(
        "import os; from app.database_safety import is_protected_database; "
        "print(is_protected_database(os.environ['DATABASE_URL']))",
        cwd=tmp_path,
        env={
            "DATABASE_URL": f"sqlite:///{alternate}",
            "PROTECTED_DATABASE_PATHS": str(protected),
        },
    )
    assert result.returncode == 0, _output(result)
    assert "True" in result.stdout


def test_t12_default_startup_does_not_create_schema(tmp_path: Path):
    database = tmp_path / "default-startup.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={"APP_ENV": "test", "DATABASE_URL": _sqlite_url(database)},
    )
    assert result.returncode != 0
    assert "Database schema is not ready. Run the approved migration procedure." in _output(result)
    if database.exists():
        with sqlite3.connect(database) as connection:
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert tables == []


def test_t13_exact_dev_switch_allows_create_all_on_temp_database(tmp_path: Path):
    database = tmp_path / "create-all.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "ALLOW_DEV_SCHEMA_CREATE_ALL": EXACT_CREATE_ALL,
        },
    )
    assert result.returncode == 0, _output(result)
    with sqlite3.connect(database) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"projects", "accounts", "people"}.issubset(table_names)


def test_t14_exact_dev_switch_rejects_protected_target_before_connect(tmp_path: Path):
    protected = tmp_path / "protected-create-all.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={
            "APP_ENV": "development",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
            "ALLOW_DEV_SCHEMA_CREATE_ALL": EXACT_CREATE_ALL,
        },
    )
    assert result.returncode != 0
    assert "protected" in _output(result).lower()
    assert not protected.exists()


def test_t15_production_rejects_create_all_even_with_exact_switch(tmp_path: Path):
    database = tmp_path / "production-create-all.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={
            "APP_ENV": "production",
            "DATABASE_URL": _sqlite_url(database),
            "ALLOW_DEV_SCHEMA_CREATE_ALL": EXACT_CREATE_ALL,
        },
    )
    assert result.returncode != 0
    assert "development or test" in _output(result).lower()
    assert not database.exists()


def test_truthy_but_inexact_dev_create_all_switch_is_rejected(tmp_path: Path):
    database = tmp_path / "inexact-create-all.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={
            "APP_ENV": "test",
            "DATABASE_URL": _sqlite_url(database),
            "ALLOW_DEV_SCHEMA_CREATE_ALL": "true",
        },
    )
    assert result.returncode != 0
    assert "exact development-only authorization" in _output(result).lower()
    assert not database.exists()


def test_t16_dev_seed_rejects_protected_target_before_connect(tmp_path: Path):
    protected = tmp_path / "protected-seed.db"
    result = _run_python(
        "from app.main import _startup; _startup()",
        cwd=BACKEND_ROOT,
        env={
            "APP_ENV": "development",
            "DATABASE_URL": _sqlite_url(protected),
            "PROTECTED_DATABASE_PATHS": str(protected),
            "BOWEI_DEV_MODE": "true",
        },
    )
    assert result.returncode != 0
    assert "seed" in _output(result).lower()
    assert "protected" in _output(result).lower()
    assert not protected.exists()


def test_t17_database_target_description_never_exposes_credentials(tmp_path: Path):
    password = "never-print-this-password"
    url = f"postgresql://sensitive-user:{password}@db.internal:5432/bowei"
    result = _run_python(
        "import os; from app.database_safety import describe_database_target; "
        "print(describe_database_target(os.environ['DATABASE_URL']))",
        cwd=tmp_path,
        env={"DATABASE_URL": url},
    )
    assert result.returncode == 0, _output(result)
    assert "type: postgresql" in result.stdout.lower()
    assert "host: db.internal" in result.stdout.lower()
    assert "database: bowei" in result.stdout.lower()
    assert password not in _output(result)
    assert "sensitive-user" not in _output(result)
