"""Keep the test process isolated from every repository database."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TEST_ROOT = Path(tempfile.mkdtemp(prefix="moways-pytest-"))
_TEST_DATABASE = _TEST_ROOT / "pytest-runtime.db"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE.as_posix()}"
os.environ.setdefault(
    "PROTECTED_DATABASE_PATHS",
    str((Path(__file__).resolve().parents[1] / "bowei_ai_dashboard.db").resolve()),
)
