"""Runtime settings helpers for backend auth/session and secret sources."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_COOKIE_NAME = "bowei_session"
_DEFAULT_COOKIE_SAMESITE = "lax"
_DEFAULT_SESSION_TTL_DAYS = 7
_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_ALLOWED_ORIGINS = {
    "http://127.0.0.1:6001",
    "http://localhost:6001",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5175",
}
_PASSWORDS_FILE = Path(__file__).resolve().parent.parent / "passwords.json"
_LLM_CONFIG_FILE = Path(__file__).resolve().parent.parent / "llm_configs.json"
_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}
_SAMESITE_VALUES = {"lax", "strict", "none"}
_LLM_PROVIDER_ENV_PREFIXES = {
    "anthropic": "ANTHROPIC",
    "dashscope": "DASHSCOPE",
    "deepseek": "DEEPSEEK",
    "glm": "ZHIPUAI",
}


def parse_bool(raw: str | None, default: bool | None = None) -> bool:
    """Parse common boolean env values safely."""
    if raw is None:
        if default is None:
            return False
        return default
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSEY:
        return False
    if default is not None:
        return default
    return False


def _normalize_samesite(raw: str | None) -> str:
    value = (raw or _DEFAULT_COOKIE_SAMESITE).strip().lower()
    if value not in _SAMESITE_VALUES:
        return _DEFAULT_COOKIE_SAMESITE
    return value


def _parse_ttl_days(raw: str | None) -> int:
    if raw is None or not raw.strip():
        return _DEFAULT_SESSION_TTL_DAYS
    try:
        ttl = int(raw)
    except ValueError:
        return _DEFAULT_SESSION_TTL_DAYS
    return ttl if ttl > 0 else _DEFAULT_SESSION_TTL_DAYS


def _read_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_json_env(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _allow_file_secret_fallback() -> bool:
    raw = os.getenv("ALLOW_FILE_SECRET_FALLBACK")
    if raw is not None:
        return parse_bool(raw, default=False)
    return _get_app_env() != "production"


def _get_app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower() or "development"


@dataclass(frozen=True)
class RuntimeSettings:
    app_env: str
    session_cookie_name: str
    session_cookie_secure: bool
    session_cookie_samesite: str
    session_ttl_days: int
    log_level: str
    legacy_password_login_enabled: bool
    cors_allowed_origins: tuple[str, ...]

    @property
    def session_ttl_seconds(self) -> int:
        return self.session_ttl_days * 86400


def get_settings() -> RuntimeSettings:
    app_env = _get_app_env()
    cookie_name = os.getenv("SESSION_COOKIE_NAME", _DEFAULT_COOKIE_NAME).strip() or _DEFAULT_COOKIE_NAME
    secure_raw = os.getenv("SESSION_COOKIE_SECURE")
    if secure_raw is None:
        session_cookie_secure = app_env == "production"
    else:
        session_cookie_secure = parse_bool(secure_raw, default=app_env == "production")
    return RuntimeSettings(
        app_env=app_env,
        session_cookie_name=cookie_name,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=_normalize_samesite(os.getenv("SESSION_COOKIE_SAMESITE")),
        session_ttl_days=_parse_ttl_days(os.getenv("SESSION_TTL_DAYS")),
        log_level=_normalize_loglevel(os.getenv("LOG_LEVEL")),
        legacy_password_login_enabled=legacy_password_login_enabled(),
        cors_allowed_origins=_parse_allowed_origins(os.getenv("CORS_ALLOWED_ORIGINS")),
    )


def _normalize_loglevel(raw: str | None) -> str:
    value = (raw or _DEFAULT_LOG_LEVEL).strip().upper()
    if value in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        return value
    return _DEFAULT_LOG_LEVEL


def _parse_allowed_origins(raw: str | None) -> tuple[str, ...]:
    values = set(_DEFAULT_ALLOWED_ORIGINS)
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
    if frontend_origin:
        values.add(frontend_origin.rstrip("/"))
    if raw:
        for item in raw.split(","):
            origin = item.strip().rstrip("/")
            if origin:
                values.add(origin)
    return tuple(sorted(values))


def get_auth_passwords() -> dict[str, str]:
    """Return auth password hashes with env priority and file fallback in dev."""
    users: dict[str, str] = {}

    env_users = _read_json_env(os.getenv("BOWEI_AUTH_USERS_JSON"))
    for username, password_hash in env_users.items():
        if username and password_hash:
            users[str(username)] = str(password_hash)

    admin_username = os.getenv("BOWEI_ADMIN_USERNAME", "").strip()
    admin_password_hash = os.getenv("BOWEI_ADMIN_PASSWORD_HASH", "").strip()
    if admin_username and admin_password_hash:
        users[admin_username] = admin_password_hash

    if users:
        return users
    if _allow_file_secret_fallback():
        return {str(k): str(v) for k, v in _read_json_file(_PASSWORDS_FILE).items() if k and v}
    return {}


def legacy_password_login_enabled() -> bool:
    raw = os.getenv("ALLOW_LEGACY_PASSWORD_LOGIN")
    if raw is not None:
        return parse_bool(raw, default=False)
    return _get_app_env() != "production"


def get_legacy_password_file_users() -> dict[str, str]:
    """Return users from passwords.json for migration/audit screens."""
    return {str(k): str(v) for k, v in _read_json_file(_PASSWORDS_FILE).items() if k and v}


def get_llm_env_config(provider: str) -> dict[str, str]:
    """Return env-based LLM overrides for a provider."""
    provider = (provider or "").strip().lower()
    prefix = _LLM_PROVIDER_ENV_PREFIXES.get(provider, provider.upper() or "LLM")
    values = {
        "api_key": os.getenv("LLM_API_KEY", "").strip() or os.getenv(f"{prefix}_API_KEY", "").strip(),
        "base_url": os.getenv("LLM_BASE_URL", "").strip() or os.getenv(f"{prefix}_BASE_URL", "").strip(),
        "model": os.getenv("LLM_MODEL", "").strip() or os.getenv(f"{prefix}_MODEL", "").strip(),
    }
    return {key: value for key, value in values.items() if value}


def get_llm_file_configs() -> dict:
    if not _allow_file_secret_fallback():
        return {}
    return _read_json_file(_LLM_CONFIG_FILE)


def get_llm_effective_config(provider: str, defaults: dict[str, str]) -> dict[str, str]:
    """Merge env overrides, file fallback, and provider defaults."""
    provider = (provider or "").strip().lower()
    effective = dict(defaults)
    file_cfg = get_llm_file_configs().get(provider, {})
    env_cfg = get_llm_env_config(provider)
    effective.update({k: v for k, v in file_cfg.items() if v is not None})
    effective.update(env_cfg)
    return effective
