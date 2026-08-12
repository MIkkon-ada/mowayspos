from __future__ import annotations

import pytest

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


def test_asr_settings_accept_custom_realtime_model(monkeypatch):
    monkeypatch.setenv("ASR_REALTIME_MODEL", "  custom-realtime-model  ")

    settings = get_asr_settings()

    assert settings.realtime_model == "custom-realtime-model"


@pytest.mark.parametrize(
    ("packet_duration_ms", "stop_timeout_seconds", "expected_packet", "expected_timeout"),
    (
        ("40", "2.0", 40, 2.0),
        ("250", "30.0", 250, 30.0),
        ("251", "30.1", 100, 8.0),
    ),
)
def test_asr_settings_enforce_inclusive_numeric_bounds(
    monkeypatch,
    packet_duration_ms,
    stop_timeout_seconds,
    expected_packet,
    expected_timeout,
):
    monkeypatch.setenv("ASR_PACKET_DURATION_MS", packet_duration_ms)
    monkeypatch.setenv("ASR_STOP_TIMEOUT_SECONDS", stop_timeout_seconds)

    settings = get_asr_settings()

    assert settings.packet_duration_ms == expected_packet
    assert settings.stop_timeout_seconds == expected_timeout
