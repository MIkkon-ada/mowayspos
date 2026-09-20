"""Start the local backend with an explicit, self-contained environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'bowei_ai_dashboard.db').resolve().as_posix()}"
# This launcher serves the parallel local frontends on ports 6004 and 6005.
# V2 owns the redirect target while both origins remain valid API callers.
os.environ["FRONTEND_ORIGIN"] = "http://127.0.0.1:6005"
# Vite's development proxy may present its target host as Origin on unsafe
# requests.  Keep this exception local to the launcher; production CORS is
# configured by its deployment environment.
os.environ["CORS_ALLOWED_ORIGINS"] = (
    "http://127.0.0.1:6004,http://localhost:6004,"
    "http://127.0.0.1:6005,http://localhost:6005,"
    "http://127.0.0.1:8011"
)

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8011)
