import os
from pathlib import Path
import subprocess
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_clean_python(source: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    database_path = (tmp_path / "auth-import-contract.db").resolve()
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
        }
    )

    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_auth_import_and_now_contract_in_clean_python_process(tmp_path: Path):
    result = _run_clean_python(
        """
from datetime import datetime, timezone
from typing import get_type_hints
from app import auth

value = auth._now()
assert isinstance(value, datetime)
assert get_type_hints(auth._now)["return"] is datetime

sentinel = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
auth.utc_now = lambda: sentinel
assert auth._now() is sentinel

print(type(value).__name__)
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "datetime"


def test_main_imports_in_clean_python_process(tmp_path: Path):
    result = _run_clean_python(
        "import app.main; print('app.main import ok')",
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "app.main import ok"
