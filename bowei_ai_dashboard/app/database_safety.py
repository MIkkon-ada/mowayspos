"""Database target validation with no database or SQLAlchemy side effects."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit


EXACT_PROTECTED_MIGRATION_AUTHORIZATION = "I_UNDERSTAND_THIS_CHANGES_PROTECTED_DATA"
EXACT_DEV_CREATE_ALL_AUTHORIZATION = "I_UNDERSTAND_THIS_IS_DEV_ONLY"
EXACT_TEST_MEMORY_AUTHORIZATION = "I_UNDERSTAND_THIS_IS_TEST_ONLY"

_FAIL_CLOSED_MESSAGE = (
    "DATABASE_URL must be explicitly configured. "
    "Refusing to use a repository database fallback."
)
_PLACEHOLDER_MARKERS = (
    "replace-with",
    "changeme",
    "change-me",
    "placeholder",
    "<database",
    "<host",
    "<password",
    "your-database",
    "your-host",
)
_SUPPORTED_NETWORK_SCHEMES = {
    "postgresql",
    "postgresql+psycopg",
    "postgresql+psycopg2",
    "mysql",
    "mysql+pymysql",
    "mariadb",
}


@dataclass(frozen=True)
class DatabaseTarget:
    kind: str
    engine_url: str = field(repr=False)
    path: Path | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    is_memory: bool = False


def _app_env() -> str:
    return os.environ.get("APP_ENV", "development").strip().lower() or "development"


def require_database_url() -> str:
    raw = os.environ.get("DATABASE_URL")
    if raw is None or not raw.strip():
        raise RuntimeError(_FAIL_CLOSED_MESSAGE)
    url = raw.strip()
    lowered = url.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError(
            f"{_FAIL_CLOSED_MESSAGE} DATABASE_URL contains a placeholder value."
        )
    return url


def _normalize_sqlite_target(url: str) -> DatabaseTarget:
    parsed = urlsplit(url)
    if parsed.netloc:
        raise RuntimeError("SQLite DATABASE_URL must use a local absolute path.")

    prefix = f"{parsed.scheme}:///"
    if not url.lower().startswith(prefix.lower()):
        raise RuntimeError("SQLite DATABASE_URL has an empty or invalid path.")
    path_text = url[len(prefix) :].split("?", 1)[0].split("#", 1)[0]
    path_text = unquote(path_text)

    if path_text == ":memory:":
        allowed = (
            _app_env() == "test"
            and os.environ.get("ALLOW_TEST_MEMORY_DATABASE", "")
            == EXACT_TEST_MEMORY_AUTHORIZATION
        )
        if not allowed:
            raise RuntimeError(
                "In-memory SQLite is allowed only in APP_ENV=test with the exact "
                "ALLOW_TEST_MEMORY_DATABASE authorization."
            )
        return DatabaseTarget(
            kind="sqlite",
            engine_url="sqlite:///:memory:",
            is_memory=True,
        )

    if not path_text:
        raise RuntimeError("SQLite DATABASE_URL has an empty path.")

    path = Path(path_text)
    if not path.is_absolute():
        raise RuntimeError("SQLite DATABASE_URL must contain an absolute path.")
    normalized = path.resolve(strict=False)
    query = f"?{parsed.query}" if parsed.query else ""
    engine_url = f"{parsed.scheme}:///{normalized.as_posix()}{query}"
    return DatabaseTarget(kind="sqlite", engine_url=engine_url, path=normalized)


def normalize_database_target(url: str) -> DatabaseTarget:
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError(_FAIL_CLOSED_MESSAGE)
    candidate = url.strip()
    parsed = urlsplit(candidate)
    scheme = parsed.scheme.lower()

    if scheme == "sqlite" or scheme.startswith("sqlite+"):
        return _normalize_sqlite_target(candidate)

    if scheme not in _SUPPORTED_NETWORK_SCHEMES:
        raise RuntimeError(f"Unrecognized database URL scheme: {scheme or '<missing>'}.")
    if not parsed.hostname:
        raise RuntimeError("Network DATABASE_URL must include a host.")
    database = unquote(parsed.path.lstrip("/"))
    if not database:
        raise RuntimeError("Network DATABASE_URL must include a database name.")
    return DatabaseTarget(
        kind=scheme,
        engine_url=candidate,
        host=parsed.hostname,
        port=parsed.port,
        database=database,
    )


def _canonical_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def protected_database_paths() -> tuple[Path, ...]:
    paths = [Path(__file__).resolve().parent.parent / "bowei_ai_dashboard.db"]
    raw = os.environ.get("PROTECTED_DATABASE_PATHS", "")
    separator = ";" if os.name == "nt" else os.pathsep
    for item in raw.split(separator):
        value = item.strip()
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            raise RuntimeError("PROTECTED_DATABASE_PATHS entries must be absolute paths.")
        paths.append(path)

    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path.resolve(strict=False)
        unique.setdefault(_canonical_path(resolved), resolved)
    return tuple(unique.values())


def is_protected_database(url: str) -> bool:
    target = normalize_database_target(url)
    if target.kind != "sqlite" or target.path is None:
        return False
    candidate = _canonical_path(target.path)
    return any(candidate == _canonical_path(path) for path in protected_database_paths())


def describe_database_target(url: str) -> str:
    target = normalize_database_target(url)
    protected = is_protected_database(url)
    if target.kind == "sqlite":
        location = ":memory:" if target.is_memory else str(target.path)
        return "\n".join(
            (
                "type: sqlite",
                f"path: {location}",
                f"protected: {str(protected).lower()}",
            )
        )

    port = f"\nport: {target.port}" if target.port is not None else ""
    return (
        f"type: {target.kind}\n"
        f"host: {target.host}{port}\n"
        f"database: {target.database}\n"
        "protected: false"
    )


def print_database_target(url: str, *, mode: str) -> None:
    if mode not in {"offline", "online", "startup"}:
        raise ValueError("Unsupported database target mode.")
    print(f"DATABASE TARGET\n{describe_database_target(url)}\nmode: {mode}", flush=True)


def ensure_application_target_allowed(url: str) -> None:
    if _app_env() == "test" and is_protected_database(url):
        raise RuntimeError(
            "Test environment cannot use a protected database. "
            "Refusing to connect before engine creation."
        )


def authorize_protected_migration(url: str) -> bool:
    if not is_protected_database(url):
        return False
    if _app_env() == "test":
        raise RuntimeError(
            "Test environment cannot migrate a protected database, even with exact authorization."
        )
    if (
        os.environ.get("ALLOW_PROTECTED_DATABASE_MIGRATION", "")
        != EXACT_PROTECTED_MIGRATION_AUTHORIZATION
    ):
        raise RuntimeError(
            "Protected database migration is not authorized. "
            "Use the approved backup and exact authorization procedure."
        )
    return True


def dev_create_all_requested() -> bool:
    return bool(os.environ.get("ALLOW_DEV_SCHEMA_CREATE_ALL", "").strip())


def authorize_dev_create_all(url: str) -> None:
    if (
        os.environ.get("ALLOW_DEV_SCHEMA_CREATE_ALL", "")
        != EXACT_DEV_CREATE_ALL_AUTHORIZATION
    ):
        raise RuntimeError(
            "ALLOW_DEV_SCHEMA_CREATE_ALL requires the exact development-only authorization."
        )
    if _app_env() not in {"development", "test"}:
        raise RuntimeError("create_all is allowed only in development or test environments.")
    if is_protected_database(url):
        raise RuntimeError("create_all is forbidden for a protected database target.")


def authorize_dev_seed(url: str) -> None:
    if _app_env() != "development":
        raise RuntimeError("Automatic seed is allowed only in development.")
    if is_protected_database(url):
        raise RuntimeError("Automatic seed is forbidden for a protected database target.")
