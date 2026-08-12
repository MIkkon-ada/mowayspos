from __future__ import annotations

import pytest

from app import main


def test_production_database_mode_requires_a_valid_ai_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AI_CAPABILITY_CENTER_MODE", "database")
    monkeypatch.delenv("AI_CONFIG_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AI_CONFIG_ENCRYPTION_KEY"):
        main._startup()
