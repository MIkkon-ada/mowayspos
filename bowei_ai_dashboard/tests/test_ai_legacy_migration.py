from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.ai_legacy_migration import import_legacy_llm_config


TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_legacy_import_is_idempotent_and_creates_disabled_policies_without_an_asr_key(
    db, tmp_path
):
    legacy = tmp_path / "llm_configs.json"
    legacy.write_text(
        json.dumps(
            {
                "default_provider": "deepseek",
                "deepseek": {
                    "enabled": True,
                    "api_key": "legacy-key",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    first = import_legacy_llm_config(db, legacy, cipher_key=TEST_FERNET_KEY)
    second = import_legacy_llm_config(db, legacy, cipher_key=TEST_FERNET_KEY)

    assert first.created_model_codes == ["migrated-deepseek-chat"]
    assert second.created_model_codes == []
    assert first.policy_states == {
        "meeting.analysis": "enabled",
        "task.extraction": "enabled",
        "project.init.analysis": "enabled",
        "speech.realtime": "disabled",
    }
    assert db.query(models.AIModel).count() == 1


def test_legacy_dashscope_import_creates_chat_and_asr_models(db, tmp_path):
    legacy = tmp_path / "llm_configs.json"
    legacy.write_text(
        json.dumps(
            {
                "default_provider": "dashscope",
                "dashscope": {
                    "enabled": True,
                    "api_key": "legacy-key",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                },
            }
        ),
        encoding="utf-8",
    )

    report = import_legacy_llm_config(db, legacy, cipher_key=TEST_FERNET_KEY)
    asr = db.query(models.AIModel).filter_by(code="migrated-dashscope-asr").one()

    assert report.created_model_codes == ["migrated-dashscope-chat", "migrated-dashscope-asr"]
    assert asr.model_type == "asr"
    assert json.loads(asr.config_json) == {
        "file_model": "paraformer-realtime-v2",
        "realtime_model": "fun-asr-realtime",
    }
    assert report.policy_states["speech.realtime"] == "enabled"
