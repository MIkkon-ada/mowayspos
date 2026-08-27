"""One-time, idempotent importer for legacy file-based LLM configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.ai.contracts import Capability
from app.ai.crypto import AICredentialCipher
from app.ai.repository import AIConfigurationRepository, InvalidAIModel, InvalidAIPolicy


LEGACY_PROVIDERS = {
    "anthropic": {
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-6",
    },
    "dashscope": {
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "deepseek": {
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "default_model": "glm-4-flash",
    },
}


@dataclass
class LegacyMigrationReport:
    created_model_codes: list[str] = field(default_factory=list)
    updated_model_codes: list[str] = field(default_factory=list)
    skipped_model_codes: list[str] = field(default_factory=list)
    policy_states: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)


def _legacy_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _usable_record(config: dict[str, Any], provider: str) -> dict[str, str] | None:
    record = config.get(provider)
    if not isinstance(record, dict) or not record.get("enabled"):
        return None
    api_key = str(record.get("api_key") or "").strip()
    if not api_key:
        return None
    metadata = LEGACY_PROVIDERS[provider]
    return {
        "api_key": api_key,
        "base_url": str(record.get("base_url") or metadata["default_base_url"]).strip(),
        "model_name": str(record.get("model") or metadata["default_model"]).strip(),
    }


def _credential_matches(
    db: Session, model_id: int, cipher: AICredentialCipher, api_key: str
) -> bool:
    credential = db.query(models.AIModelCredential).filter_by(model_id=model_id).one_or_none()
    if credential is None or not credential.encrypted_api_key:
        return False
    try:
        return cipher.decrypt(credential.encrypted_api_key) == api_key
    except Exception:
        return False


def _upsert_migrated_model(
    repo: AIConfigurationRepository,
    db: Session,
    cipher: AICredentialCipher,
    report: LegacyMigrationReport,
    *,
    code: str,
    provider: str,
    display_name: str,
    model_name: str,
    model_type: str,
    base_url: str,
    config: dict[str, Any],
    api_key: str,
) -> models.AIModel | None:
    existing = db.query(models.AIModel).filter_by(code=code).one_or_none()
    if existing is not None and (
        existing.source != "migrated" or existing.managed_by != "legacy-import"
    ):
        report.skipped_model_codes.append(code)
        report.reasons[code] = "existing model is not legacy-import managed"
        return None

    if existing is None:
        model = repo.create_model(
            code=code,
            display_name=display_name,
            provider=provider,
            model_name=model_name,
            model_type=model_type,
            base_url=base_url,
            config=config,
            enabled=True,
            source="migrated",
        )
        model.managed_by = "legacy-import"
        repo.replace_credential(model.id, api_key=api_key, app_secret=None)
        report.created_model_codes.append(code)
        return model

    changes = {
        "display_name": display_name,
        "provider": provider,
        "model_name": model_name,
        "model_type": model_type,
        "base_url": base_url,
        "config": config,
        "enabled": True,
        "source": "migrated",
        "managed_by": "legacy-import",
    }
    before_revision = existing.revision
    repo.update_model(existing.id, **changes)
    credential_changed = not _credential_matches(db, existing.id, cipher, api_key)
    if credential_changed:
        repo.replace_credential(existing.id, api_key=api_key, app_secret=None)
    if existing.revision != before_revision or credential_changed:
        report.updated_model_codes.append(code)
    return existing


def import_legacy_llm_config(
    db: Session, legacy_path: Path, *, cipher_key: str
) -> LegacyMigrationReport:
    """Import usable legacy records without returning or persisting plaintext secrets."""

    config = _legacy_config(Path(legacy_path))
    report = LegacyMigrationReport()
    repo = AIConfigurationRepository(db, cipher_key=cipher_key)
    cipher = AICredentialCipher(cipher_key)
    chat_models: dict[str, models.AIModel] = {}
    asr_model: models.AIModel | None = None

    for provider in LEGACY_PROVIDERS:
        record = _usable_record(config, provider)
        if record is None:
            continue
        chat = _upsert_migrated_model(
            repo,
            db,
            cipher,
            report,
            code=f"migrated-{provider}-chat",
            provider=provider,
            display_name=f"Migrated {provider} chat",
            model_name=record["model_name"],
            model_type="chat",
            base_url=record["base_url"],
            config={},
            api_key=record["api_key"],
        )
        if chat is not None:
            chat_models[provider] = chat

        if provider == "dashscope":
            asr_model = _upsert_migrated_model(
                repo,
                db,
                cipher,
                report,
                code="migrated-dashscope-asr",
                provider="dashscope",
                display_name="Migrated dashscope ASR",
                model_name="paraformer-realtime-v2",
                model_type="asr",
                base_url=record["base_url"],
                config={
                    "file_model": "paraformer-realtime-v2",
                    "realtime_model": "fun-asr-realtime",
                },
                api_key=record["api_key"],
            )

    default_provider = str(config.get("default_provider") or "").strip().lower()
    primary_chat = chat_models.get(default_provider)
    if primary_chat is None and chat_models:
        primary_chat = next(iter(chat_models.values()))

    for capability_key in (Capability.MEETING_ANALYSIS, Capability.TASK_EXTRACTION):
        _save_missing_migration_policy(repo, db, report, capability_key, primary_chat)
    project_init_primary = chat_models.get("deepseek") or primary_chat
    project_init_fallback = (
        chat_models.get("dashscope")
        if project_init_primary is not None and project_init_primary.provider == "deepseek"
        else None
    )
    _save_missing_migration_policy(
        repo,
        db,
        report,
        Capability.PROJECT_INIT_ANALYSIS,
        project_init_primary,
        fallback_models=[project_init_fallback] if project_init_fallback is not None else [],
    )
    _save_missing_migration_policy(repo, db, report, Capability.SPEECH_REALTIME, asr_model)
    db.flush()
    return report


def _save_missing_migration_policy(
    repo: AIConfigurationRepository,
    db: Session,
    report: LegacyMigrationReport,
    capability_key: str,
    primary_model: models.AIModel | None,
    fallback_models: list[models.AIModel] | None = None,
) -> None:
    existing = (
        db.query(models.AICapabilityPolicy).filter_by(capability_key=capability_key).one_or_none()
    )
    if existing is not None:
        report.policy_states[capability_key] = "enabled" if existing.enabled else "disabled"
        report.reasons[capability_key] = "existing capability policy was preserved"
        return
    enabled = primary_model is not None
    fallback_ids = [model.id for model in (fallback_models or [])]
    try:
        policy = repo.save_policy(
            capability_key,
            primary_model_id=primary_model.id if primary_model is not None else None,
            fallback_model_ids=fallback_ids,
            timeout_seconds=60,
            max_attempts=1 + len(fallback_ids),
            enabled=enabled,
        )
    except (InvalidAIModel, InvalidAIPolicy):
        policy = repo.save_policy(
            capability_key,
            primary_model_id=None,
            fallback_model_ids=[],
            timeout_seconds=60,
            max_attempts=1,
            enabled=False,
        )
        report.reasons[capability_key] = "no compatible usable legacy model"
    report.policy_states[capability_key] = "enabled" if policy.enabled else "disabled"
