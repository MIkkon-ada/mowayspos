from __future__ import annotations

from app.settings import get_asr_settings


_ASR_ENV_VARS = (
    "ASR_REALTIME_MODEL",
    "ASR_CONTEXT_ENABLED",
    "ASR_PACKET_DURATION_MS",
    "ASR_STOP_TIMEOUT_SECONDS",
    "ASR_HEARTBEAT_ENABLED",
)


def test_asr_settings_use_safe_defaults(monkeypatch):
    for name in _ASR_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    settings = get_asr_settings()

    assert settings.realtime_model == "fun-asr-realtime"
    assert settings.context_enabled is True
    assert settings.packet_duration_ms == 100
    assert settings.stop_timeout_seconds == 8.0
    assert settings.heartbeat_enabled is True


def test_asr_settings_normalize_invalid_numbers_and_parse_booleans(monkeypatch):
    monkeypatch.setenv("ASR_PACKET_DURATION_MS", "3")
    monkeypatch.setenv("ASR_STOP_TIMEOUT_SECONDS", "invalid")
    monkeypatch.setenv("ASR_CONTEXT_ENABLED", "false")
    monkeypatch.setenv("ASR_HEARTBEAT_ENABLED", "0")

    settings = get_asr_settings()

    assert settings.packet_duration_ms == 100
    assert settings.stop_timeout_seconds == 8.0
    assert settings.context_enabled is False
    assert settings.heartbeat_enabled is False
