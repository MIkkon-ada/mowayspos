from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.contracts import Capability, ModelType
from app.ai.service import AIService
from app.database import Base
from app.services.ai_legacy_migration import import_legacy_llm_config


TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="


def test_legacy_json_migrates_to_database_and_all_capabilities_are_resolvable(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    legacy = tmp_path / "legacy-ai-config.json"
    legacy.write_text(
        json.dumps(
            {
                "default_provider": "dashscope",
                "dashscope": {
                    "enabled": True,
                    "api_key": "test-key",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        report = import_legacy_llm_config(db, legacy, cipher_key=TEST_FERNET_KEY)
        db.commit()

        assert report.policy_states == {
            Capability.MEETING_ANALYSIS: "enabled",
            Capability.TASK_EXTRACTION: "enabled",
            Capability.PROJECT_INIT_ANALYSIS: "enabled",
            Capability.SPEECH_REALTIME: "enabled",
        }
        service = AIService(db, cipher_key=TEST_FERNET_KEY)
        for capability_key, model_type in (
            (Capability.MEETING_ANALYSIS, ModelType.CHAT),
            (Capability.TASK_EXTRACTION, ModelType.CHAT),
            (Capability.PROJECT_INIT_ANALYSIS, ModelType.CHAT),
            (Capability.SPEECH_REALTIME, ModelType.ASR),
        ):
            _policy, candidates = service._candidates(capability_key, model_type)
            assert candidates[0].model_type == model_type.value
    finally:
        db.close()
        Base.metadata.drop_all(engine)
