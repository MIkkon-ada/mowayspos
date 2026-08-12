# AI能力配置升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace file/provider-driven AI configuration with an encrypted database-backed AI capability center that routes the current meeting, task extraction, project-initialization, and speech-transcription capability domains through explicit policies.

**Architecture:** Create a small AI configuration domain with four persisted resources: models, credentials, capability policies, and invocation logs. A single `AIService` resolves an enabled policy and calls a typed chat or ASR adapter, trying only configured fallbacks for retryable failures. Existing prompts and business-output validation remain in their current services; only configuration lookup, Provider selection, credential handling, and invocation auditing move to the new domain.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, `cryptography`/Fernet, OpenAI SDK, Anthropic SDK, DashScope SDK, React 19, TypeScript, Node test runner, pytest.

---

## Locked design decisions

- Database rows are the only normal runtime configuration source. `llm_configs.json` is a one-time migration input and emergency rollback source only.
- The model type is `chat` or `asr` in this release. The schema permits future types, but RAG, embedding, rerank, VLM, and MCP are out of scope.
- The first release registers exactly four top-level capability keys: `meeting.analysis`, `task.extraction`, `project.init.analysis`, and `speech.realtime`. A policy is global, not project- or user-scoped.
- A disabled policy may have no primary model during migration. An enabled policy must have one enabled, credential-configured primary model of the required type. This is the only allowed nullable-primary state.
- Secrets use Fernet encryption with a required `AI_CONFIG_ENCRYPTION_KEY`; there is no plaintext fallback. Production starts in database mode only when the key is valid.
- Chat fallback happens for timeout, connection, rate-limit, and upstream-5xx failures. Schema/input/output validation failures do not fall back. Realtime ASR may select a fallback only before audio is accepted; it never switches mid-stream.
- The invocation log stores metadata and sanitized error codes only. It never stores prompts, audio, complete model responses, API keys, authorization headers, or raw upstream exception text.

## Target file structure

| File | Responsibility |
| --- | --- |
| `bowei_ai_dashboard/app/ai/contracts.py` | Capability constants, typed requests/results, stable error codes, retry classification |
| `bowei_ai_dashboard/app/ai/crypto.py` | Encryption-key validation and credential encrypt/decrypt helpers |
| `bowei_ai_dashboard/app/ai/repository.py` | Database queries and persistence operations for AI resources |
| `bowei_ai_dashboard/app/ai/adapters.py` | Provider-specific chat/file-ASR/realtime-ASR invocations behind typed interfaces |
| `bowei_ai_dashboard/app/ai/service.py` | Policy resolution, fallback orchestration, audit logging, and public `AIService` API |
| `bowei_ai_dashboard/app/services/ai_legacy_migration.py` | Idempotent `llm_configs.json` importer and structured migration report |
| `bowei_ai_dashboard/app/routers/ai_config.py` | Tech-admin model, credential, policy, test, migration-report, and log APIs |
| `bowei_ai_dashboard/app/models.py` | SQLAlchemy models for the four AI configuration tables |
| `bowei_ai_dashboard/app/schemas.py` | Strict API request/response models for the AI configuration center |
| `bowei_ai_dashboard/app/routers/meetings.py` | Call `AIService` for `meeting.analysis` |
| `bowei_ai_dashboard/app/services/extractor.py` | Call `AIService` for `task.extraction` |
| `bowei_ai_dashboard/app/services/work_report_agent.py` | Accept a typed AI caller rather than a Provider string |
| `bowei_ai_dashboard/app/services/project_init_ai_agent.py` | Call `AIService` for `project.init.analysis` |
| `bowei_ai_dashboard/app/routers/transcribe.py` | Call `AIService` for `speech.realtime` file and stream entry points |
| `frontend/src/api/aiConfig.ts` | Typed client for the new admin API |
| `frontend/src/features/settings/AIConfigurationSection.tsx` | Model, credential-status, and capability-policy management UI |
| `frontend/src/pages/SettingsPage.tsx` | Replace the legacy LLM card with the capability-center card |
| `bowei_ai_dashboard/migrations/versions/a6b7c8d9e0f1_add_ai_capability_configuration.py` | Create four tables, indexes, and constraints |

The legacy `app/llm_config.py`, `routers/llm_config.py`, `frontend/src/api/llmConfig.ts`, and `LLMConfigSection.tsx` remain only during the compatibility release, then are deleted in the final cleanup task after the database path is verified.

### Task 1: Define the AI domain contracts and encrypted-secret boundary

**Files:**
- Create: `bowei_ai_dashboard/app/ai/__init__.py`
- Create: `bowei_ai_dashboard/app/ai/contracts.py`
- Create: `bowei_ai_dashboard/app/ai/crypto.py`
- Modify: `bowei_ai_dashboard/requirements.txt`
- Create: `bowei_ai_dashboard/tests/test_ai_config_crypto.py`
- Create: `bowei_ai_dashboard/tests/test_ai_contracts.py`

- [ ] **Step 1: Write the failing contract and encryption tests**

```python
from cryptography.fernet import Fernet
import pytest

from app.ai.contracts import Capability, ModelType, classify_retryable_error
from app.ai.crypto import AICredentialCipher, AIConfigurationKeyError


def test_capability_registry_requires_chat_for_meeting_and_asr_for_speech():
    assert Capability.required_model_type("meeting.analysis") is ModelType.CHAT
    assert Capability.required_model_type("speech.realtime") is ModelType.ASR
    with pytest.raises(ValueError, match="unsupported AI capability"):
        Capability.required_model_type("unknown.capability")


def test_cipher_round_trip_never_returns_plaintext_as_ciphertext():
    cipher = AICredentialCipher(Fernet.generate_key().decode())
    token = cipher.encrypt("secret-value")
    assert token != "secret-value"
    assert cipher.decrypt(token) == "secret-value"


def test_cipher_rejects_missing_or_invalid_key():
    with pytest.raises(AIConfigurationKeyError):
        AICredentialCipher("")
    with pytest.raises(AIConfigurationKeyError):
        AICredentialCipher("not-a-fernet-key")


@pytest.mark.parametrize("status,retryable", [(408, True), (429, True), (500, True), (503, True), (400, False), (401, False), (422, False)])
def test_retry_classifier_only_retries_transient_upstream_statuses(status, retryable):
    assert classify_retryable_error(status_code=status) is retryable
```

- [ ] **Step 2: Run the new tests and verify they fail because the AI package does not exist**

Run: `python -m pytest tests/test_ai_config_crypto.py tests/test_ai_contracts.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai'`.

- [ ] **Step 3: Add the locked cryptography dependency and domain types**

Add this line to `bowei_ai_dashboard/requirements.txt` in alphabetical order:

```text
cryptography==46.0.5
```

Create `contracts.py` with these public types and no SDK imports:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ModelType(StrEnum):
    CHAT = "chat"
    ASR = "asr"


class Capability:
    MEETING_ANALYSIS = "meeting.analysis"
    TASK_EXTRACTION = "task.extraction"
    PROJECT_INIT_ANALYSIS = "project.init.analysis"
    SPEECH_REALTIME = "speech.realtime"
    _TYPES = {
        MEETING_ANALYSIS: ModelType.CHAT,
        TASK_EXTRACTION: ModelType.CHAT,
        PROJECT_INIT_ANALYSIS: ModelType.CHAT,
        SPEECH_REALTIME: ModelType.ASR,
    }

    @classmethod
    def required_model_type(cls, capability_key: str) -> ModelType:
        try:
            return cls._TYPES[capability_key]
        except KeyError as exc:
            raise ValueError(f"unsupported AI capability: {capability_key}") from exc


class AIServiceError(RuntimeError):
    code = "AI_SERVICE_ERROR"
    retryable = False


class AICapabilityNotConfigured(AIServiceError):
    code = "AI_CAPABILITY_NOT_CONFIGURED"


class AIUpstreamError(AIServiceError):
    def __init__(self, code: str, *, retryable: bool, message: str = "AI upstream request failed"):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class AIInvocationContext:
    actor: str = ""
    resource_type: str = ""
    resource_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Implement `AICredentialCipher` with `cryptography.fernet.Fernet`; map missing, malformed, and decryption failures to `AIConfigurationKeyError` without including a token or key in the exception text. Implement `classify_retryable_error` as the explicit status set exercised by the test plus `None` for network/timeouts.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `python -m pytest tests/test_ai_config_crypto.py tests/test_ai_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the isolated foundation**

```bash
git add bowei_ai_dashboard/requirements.txt bowei_ai_dashboard/app/ai/__init__.py bowei_ai_dashboard/app/ai/contracts.py bowei_ai_dashboard/app/ai/crypto.py bowei_ai_dashboard/tests/test_ai_config_crypto.py bowei_ai_dashboard/tests/test_ai_contracts.py
git commit -m "feat: define AI capability configuration contracts"
```

### Task 2: Persist models, encrypted credentials, policies, and invocation logs

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Create: `bowei_ai_dashboard/migrations/versions/a6b7c8d9e0f1_add_ai_capability_configuration.py`
- Create: `bowei_ai_dashboard/tests/test_ai_config_models.py`
- Create: `bowei_ai_dashboard/tests/test_ai_config_migration.py`

- [ ] **Step 1: Write failing persistence and migration tests**

```python
from sqlalchemy import inspect

from app import models


def test_ai_models_enforce_unique_stable_code(db):
    db.add(models.AIModel(code="deepseek-chat-primary", display_name="DeepSeek", provider="deepseek", model_name="deepseek-chat", model_type="chat", enabled=True, source="custom"))
    db.commit()
    db.add(models.AIModel(code="deepseek-chat-primary", display_name="Duplicate", provider="deepseek", model_name="deepseek-chat", model_type="chat", enabled=True, source="custom"))
    try:
        db.commit()
        assert False, "duplicate model code must fail"
    except Exception:
        db.rollback()


def test_ai_policy_is_unique_per_capability_and_log_has_no_payload_columns(db):
    db.add(models.AICapabilityPolicy(capability_key="meeting.analysis", enabled=False, policy_version=1))
    db.commit()
    assert inspect(db.bind).has_table("ai_invocation_logs")
    fields = {column.name for column in models.AIInvocationLog.__table__.columns}
    assert {"prompt", "raw_response", "audio", "api_key"}.isdisjoint(fields)
```

`test_ai_config_migration.py` must upgrade a fresh SQLite database to `a6b7c8d9e0f1`, assert all four tables and the `uq_ai_models_code` / `uq_ai_capability_policies_key` unique constraints exist, then downgrade once and assert the tables no longer exist.

- [ ] **Step 2: Run the tests and verify they fail because the models and revision are missing**

Run: `python -m pytest tests/test_ai_config_models.py tests/test_ai_config_migration.py -q`

Expected: FAIL with missing `AIModel` and missing Alembic revision.

- [ ] **Step 3: Add SQLAlchemy models and an explicit Alembic revision**

Append these four models near the other configuration/audit models in `app/models.py`:

```python
class AIModel(Base, TimestampMixin):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("code", name="uq_ai_models_code"),)

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(96), nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    provider = Column(String(64), nullable=False, index=True)
    model_name = Column(String(160), nullable=False)
    model_type = Column(String(24), nullable=False, index=True)
    base_url = Column(Text, nullable=False, default="")
    config_json = Column(Text, nullable=False, default="{}")
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    source = Column(String(24), nullable=False, default="custom", index=True)
    managed_by = Column(String(24), nullable=False, default="")
    revision = Column(Integer, nullable=False, default=1)


class AIModelCredential(Base, TimestampMixin):
    __tablename__ = "ai_model_credentials"
    __table_args__ = (UniqueConstraint("model_id", name="uq_ai_model_credentials_model"),)

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False, index=True)
    encrypted_api_key = Column(Text, nullable=False, default="")
    encrypted_app_secret = Column(Text, nullable=False, default="")
    key_version = Column(String(32), nullable=False, default="v1")


class AICapabilityPolicy(Base, TimestampMixin):
    __tablename__ = "ai_capability_policies"
    __table_args__ = (UniqueConstraint("capability_key", name="uq_ai_capability_policies_key"),)

    id = Column(Integer, primary_key=True, index=True)
    capability_key = Column(String(96), nullable=False, index=True)
    primary_model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=True, index=True)
    fallback_model_ids_json = Column(Text, nullable=False, default="[]")
    timeout_seconds = Column(Integer, nullable=False, default=60)
    max_attempts = Column(Integer, nullable=False, default=1)
    policy_version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=False, index=True)


class AIInvocationLog(Base, TimestampMixin):
    __tablename__ = "ai_invocation_logs"

    id = Column(Integer, primary_key=True, index=True)
    capability_key = Column(String(96), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=True, index=True)
    model_revision = Column(Integer, nullable=False, default=0)
    attempt_no = Column(Integer, nullable=False, default=1)
    status = Column(String(24), nullable=False, index=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    duration_ms = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=False, default="", index=True)
    resource_type = Column(String(64), nullable=False, default="", index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    actor = Column(String(50), nullable=False, default="", index=True)
```

Create revision `a6b7c8d9e0f1` with `down_revision = "f5a6b7c8d9e0"` for the currently checked-out migration graph. Use `op.create_table`, explicit foreign keys, the named unique constraints above, and indexes for every `index=True` column. Its `downgrade()` must drop indexes before tables in this order: logs, policies, credentials, models. If the migration head changes before execution, preserve the new revision ID but replace only `down_revision` with the then-current single head after running `python -m alembic heads` from `bowei_ai_dashboard`.

- [ ] **Step 4: Run the persistence and migration tests**

Run: `python -m pytest tests/test_ai_config_models.py tests/test_ai_config_migration.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the schema contract**

```bash
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/a6b7c8d9e0f1_add_ai_capability_configuration.py bowei_ai_dashboard/tests/test_ai_config_models.py bowei_ai_dashboard/tests/test_ai_config_migration.py
git commit -m "feat: persist AI models and capability policies"
```

### Task 3: Implement configuration repository validation and the idempotent legacy importer

**Files:**
- Create: `bowei_ai_dashboard/app/ai/repository.py`
- Create: `bowei_ai_dashboard/app/services/ai_legacy_migration.py`
- Create: `bowei_ai_dashboard/tests/test_ai_config_repository.py`
- Create: `bowei_ai_dashboard/tests/test_ai_legacy_migration.py`

- [ ] **Step 1: Write failing repository and importer tests**

```python
import json

from app.ai.repository import AIConfigurationRepository, InvalidAIPolicy
from app.services.ai_legacy_migration import import_legacy_llm_config


def test_policy_rejects_mismatched_model_type_and_duplicate_fallback(db):
    repo = AIConfigurationRepository(db, cipher_key="m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U=")
    chat = repo.create_model(code="chat", display_name="chat", provider="deepseek", model_name="deepseek-chat", model_type="chat", base_url="https://api.deepseek.com", config={}, enabled=True, source="custom")
    repo.replace_credential(chat.id, api_key="key", app_secret=None)
    with pytest.raises(InvalidAIPolicy, match="requires asr"):
        repo.save_policy("speech.realtime", primary_model_id=chat.id, fallback_model_ids=[], timeout_seconds=30, max_attempts=1, enabled=True)
    with pytest.raises(InvalidAIPolicy, match="duplicate"):
        repo.save_policy("meeting.analysis", primary_model_id=chat.id, fallback_model_ids=[chat.id], timeout_seconds=30, max_attempts=2, enabled=True)


def test_legacy_import_is_idempotent_and_creates_disabled_policies_without_a_chat_key(db, tmp_path):
    legacy = tmp_path / "llm_configs.json"
    legacy.write_text(json.dumps({"default_provider": "deepseek", "deepseek": {"enabled": True, "api_key": "legacy-key", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"}}, ensure_ascii=False), encoding="utf-8")
    first = import_legacy_llm_config(db, legacy, cipher_key="m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U=")
    second = import_legacy_llm_config(db, legacy, cipher_key="m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U=")
    assert first.created_model_codes == ["migrated-deepseek-chat"]
    assert second.created_model_codes == []
    assert first.policy_states["meeting.analysis"] == "enabled"
    assert first.policy_states["speech.realtime"] == "disabled"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_ai_config_repository.py tests/test_ai_legacy_migration.py -q`

Expected: FAIL with missing repository/importer modules.

- [ ] **Step 3: Implement repository invariants and migration mapping**

Implement the following public repository operations:

```python
class AIConfigurationRepository:
    def create_model(self, *, code: str, display_name: str, provider: str, model_name: str, model_type: str, base_url: str, config: dict, enabled: bool, source: str) -> models.AIModel:
        raise NotImplementedError

    def update_model(self, model_id: int, **changes: object) -> models.AIModel:
        raise NotImplementedError

    def replace_credential(self, model_id: int, *, api_key: str | None, app_secret: str | None) -> models.AIModelCredential:
        raise NotImplementedError

    def clear_credential_field(self, model_id: int, field: str) -> None:
        raise NotImplementedError

    def credential_configured(self, model_id: int) -> bool:
        raise NotImplementedError

    def save_policy(self, capability_key: str, *, primary_model_id: int | None, fallback_model_ids: list[int], timeout_seconds: int, max_attempts: int, enabled: bool) -> models.AICapabilityPolicy:
        raise NotImplementedError
```

The repository must reject blank codes, unknown capabilities, unsupported model types, invalid HTTP(S) base URLs, negative/zero timeout, `max_attempts < 1`, duplicate fallbacks, the primary model appearing as a fallback, non-existent models, disabled referenced models, type mismatch, and enabling a policy without an eligible primary model with a configured credential. On a successful material model update increment `revision`; on a successful material policy update increment `policy_version`. A credential replacement does not return a secret and increments the owning model revision.

Implement `import_legacy_llm_config(db, legacy_path, cipher_key)` with this exact mapping:

```text
legacy provider record enabled + API key
  -> migrated-{provider}-chat, source=migrated, managed_by=legacy-import

legacy dashscope record enabled + API key
  -> migrated-dashscope-asr, model_type=asr,
     model_name=paraformer-realtime-v2,
     config_json={"file_model":"paraformer-realtime-v2","realtime_model":"fun-asr-realtime"}

usable default_provider, otherwise first usable provider in PROVIDERS declaration order
  -> same primary chat model for meeting.analysis, task.extraction, project.init.analysis

usable migrated-dashscope-asr
  -> primary model for speech.realtime
```

Create every missing capability policy. Leave a policy disabled with `primary_model_id=None` when no compatible usable model exists. Only modify records whose `source == "migrated"` and `managed_by == "legacy-import"`; never overwrite `custom`, `builtin`, or administrator-taken-over records. Return a `LegacyMigrationReport` containing codes created/updated/skipped, per-capability state, and sanitized reasons; do not include keys.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/test_ai_config_repository.py tests/test_ai_legacy_migration.py -q`

Expected: PASS.

- [ ] **Step 5: Commit repository and importer**

```bash
git add bowei_ai_dashboard/app/ai/repository.py bowei_ai_dashboard/app/services/ai_legacy_migration.py bowei_ai_dashboard/tests/test_ai_config_repository.py bowei_ai_dashboard/tests/test_ai_legacy_migration.py
git commit -m "feat: migrate legacy AI configuration into database"
```

### Task 4: Build typed Provider adapters, policy fallback, and sanitized invocation auditing

**Files:**
- Create: `bowei_ai_dashboard/app/ai/adapters.py`
- Create: `bowei_ai_dashboard/app/ai/service.py`
- Create: `bowei_ai_dashboard/tests/test_ai_service.py`
- Create: `bowei_ai_dashboard/tests/test_ai_invocation_logs.py`

- [ ] **Step 1: Write failing AI service tests using fake adapters**

```python
from app.ai.contracts import AIInvocationContext, AIUpstreamError, Capability
from app.ai.service import AIService


def test_chat_uses_primary_then_retryable_fallback_and_logs_each_attempt(db, configured_chat_policy, fake_adapters):
    primary, fallback = configured_chat_policy
    fake_adapters.chat_errors[primary.id] = AIUpstreamError("AI_UPSTREAM_TIMEOUT", retryable=True)
    fake_adapters.chat_results[fallback.id] = '{"title":"ok"}'

    result = AIService(db, adapters=fake_adapters).invoke_chat(
        Capability.MEETING_ANALYSIS, "prompt", AIInvocationContext(actor="pm", resource_type="meeting", resource_id=8)
    )

    assert result.text == '{"title":"ok"}'
    logs = db.query(models.AIInvocationLog).order_by(models.AIInvocationLog.attempt_no).all()
    assert [(row.status, row.error_code, row.fallback_used) for row in logs] == [
        ("failed", "AI_UPSTREAM_TIMEOUT", False), ("succeeded", "", True),
    ]


def test_non_retryable_schema_error_does_not_try_fallback(db, configured_chat_policy, fake_adapters):
    primary, fallback = configured_chat_policy
    fake_adapters.chat_errors[primary.id] = AIUpstreamError("AI_UPSTREAM_BAD_REQUEST", retryable=False)
    with pytest.raises(AIUpstreamError, match="AI upstream request failed"):
        AIService(db, adapters=fake_adapters).invoke_chat(Capability.TASK_EXTRACTION, "prompt")
    assert fake_adapters.chat_calls == [primary.id]


def test_logs_never_contain_prompt_secret_or_raw_exception_text(db, configured_chat_policy, fake_adapters):
    secret = "do-not-log-me"
    fake_adapters.chat_errors[configured_chat_policy[0].id] = AIUpstreamError("AI_UPSTREAM_5XX", retryable=True, message=f"upstream {secret}")
    with pytest.raises(Exception):
        AIService(db, adapters=fake_adapters).invoke_chat(Capability.MEETING_ANALYSIS, f"prompt {secret}")
    assert secret not in repr(db.query(models.AIInvocationLog).all())
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_ai_service.py tests/test_ai_invocation_logs.py -q`

Expected: FAIL with missing `AIService` and adapter interfaces.

- [ ] **Step 3: Implement the adapters and service boundary**

Expose these adapter protocols and keep SDK calls inside their concrete implementations only:

```python
class ChatAdapter(Protocol):
    def complete(self, model: models.AIModel, api_key: str, prompt: str, *, timeout_seconds: int) -> str:
        raise NotImplementedError

class FileASRAdapter(Protocol):
    def transcribe(self, model: models.AIModel, api_key: str, content: bytes, filename: str, *, timeout_seconds: int) -> str:
        raise NotImplementedError

class RealtimeASRAdapter(Protocol):
    def create_session(self, model: models.AIModel, api_key: str, *, settings: AsrSettings, context: str) -> DashScopeRealtimeAsr:
        raise NotImplementedError
```

`OpenAICompatibleChatAdapter` must support DeepSeek, DashScope, and GLM through `OpenAI`; `AnthropicChatAdapter` must use the Anthropic client. `DashScopeFileASRAdapter` must move the current `_do_transcribe` body out of `routers/transcribe.py`, use `model.config_json["file_model"]` with a default of `paraformer-realtime-v2`, and clean up the temporary file in `finally`. Convert SDK exceptions to `AIUpstreamError` using fixed codes only: `AI_UPSTREAM_TIMEOUT`, `AI_UPSTREAM_RATE_LIMIT`, `AI_UPSTREAM_5XX`, `AI_UPSTREAM_CONNECTION`, `AI_UPSTREAM_BAD_REQUEST`, `AI_UPSTREAM_AUTH`, and `AI_UPSTREAM_UNKNOWN`.

Implement the public service API:

```python
class AIService:
    def invoke_chat(self, capability_key: str, prompt: str, context: AIInvocationContext | None = None) -> ChatResult:
        raise NotImplementedError

    def transcribe_file(self, capability_key: str, content: bytes, filename: str, context: AIInvocationContext | None = None) -> ASRResult:
        raise NotImplementedError

    def create_realtime_asr_session(self, capability_key: str, *, settings: AsrSettings, context_text: str, context: AIInvocationContext | None = None) -> RealtimeASRHandle:
        raise NotImplementedError
```

For each operation, resolve one enabled policy, construct `[primary, *fallbacks][:max_attempts]`, decrypt credentials only immediately before adapter use, and add one `AIInvocationLog` row per attempt. `duration_ms` uses monotonic elapsed time. For realtime ASR, `RealtimeASRHandle.start()` may retry a fallback only if the first `session.start()` fails before the router begins accepting binary frames; after successful start it proxies the one selected session without mid-stream switching.

- [ ] **Step 4: Run service, audit, and existing ASR tests**

Run: `python -m pytest tests/test_ai_service.py tests/test_ai_invocation_logs.py tests/test_realtime_asr.py tests/test_asr_settings.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the runtime boundary**

```bash
git add bowei_ai_dashboard/app/ai/adapters.py bowei_ai_dashboard/app/ai/service.py bowei_ai_dashboard/tests/test_ai_service.py bowei_ai_dashboard/tests/test_ai_invocation_logs.py
git commit -m "feat: route AI calls through capability policies"
```

### Task 5: Expose a tech-admin AI configuration API with separate credential operations

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/app/routers/ai_config.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Create: `bowei_ai_dashboard/tests/test_ai_config_api.py`

- [ ] **Step 1: Write failing API contract tests**

```python
def test_non_admin_cannot_manage_models(client, member_cookie):
    assert client.get("/api/ai-config/models", cookies=member_cookie).status_code == 403


def test_admin_can_create_model_and_only_sees_credential_status(client, admin_cookie):
    created = client.post("/api/ai-config/models", cookies=admin_cookie, json={
        "code": "deepseek-chat-primary", "display_name": "DeepSeek 主模型", "provider": "deepseek",
        "model_name": "deepseek-chat", "model_type": "chat", "base_url": "https://api.deepseek.com",
        "config": {}, "enabled": True, "source": "custom",
    })
    assert created.status_code == 201
    model_id = created.json()["id"]
    saved = client.put(f"/api/ai-config/models/{model_id}/credentials", cookies=admin_cookie, json={"api_key": "never-return-this"})
    assert saved.status_code == 200
    listed = client.get("/api/ai-config/models", cookies=admin_cookie)
    assert listed.json()[0]["credential_configured"] is True
    assert "never-return-this" not in listed.text


def test_policy_rejects_disabled_or_wrong_type_models(client, admin_cookie, seeded_chat_model_id):
    response = client.put("/api/ai-config/policies/speech.realtime", cookies=admin_cookie, json={
        "primary_model_id": seeded_chat_model_id, "fallback_model_ids": [], "timeout_seconds": 30, "max_attempts": 1, "enabled": True,
    })
    assert response.status_code == 422
```

- [ ] **Step 2: Run the API tests and verify they fail**

Run: `python -m pytest tests/test_ai_config_api.py -q`

Expected: FAIL with `404` because `/api/ai-config` is not registered.

- [ ] **Step 3: Add strict schemas and routes**

Add Pydantic models with `ConfigDict(extra="forbid")` for `AIModelCreate`, `AIModelUpdate`, `AICredentialWrite`, `AIPolicyWrite`, and `AIModelTestRequest`. Responses must contain only non-secret model fields plus `credential_configured`; never reuse `LLMConfigPayload`.

Register a new `APIRouter(prefix="/api/ai-config", tags=["ai-config"])` in `main.py` and protect every route with `require_tech_admin`. Implement exactly these routes:

```text
GET    /models
POST   /models                         -> 201
PUT    /models/{model_id}
PATCH  /models/{model_id}/enabled
PUT    /models/{model_id}/credentials
DELETE /models/{model_id}/credentials/{field}
POST   /models/{model_id}/test
GET    /policies
PUT    /policies/{capability_key}
GET    /invocation-logs?capability_key=&limit=100
POST   /migration/legacy-llm-config    -> explicit, idempotent import command
```

Validate base URLs through the existing SSRF-safe URL validator before persisting. The test route accepts an optional temporary key but never persists it; an absent temporary key uses the saved credential. Return only `{ "ok": true, "message": "连接成功" }` or a fixed safe error code/message. The migration route returns `LegacyMigrationReport` only and is not callable from any non-admin session.

- [ ] **Step 4: Run API and existing authorization tests**

Run: `python -m pytest tests/test_ai_config_api.py tests/test_production_runtime_security.py tests/test_auth_import_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the management API**

```bash
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/ai_config.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/tests/test_ai_config_api.py
git commit -m "feat: add AI capability configuration API"
```

### Task 6: Replace the legacy settings card with a model-and-policy management UI

**Files:**
- Create: `frontend/src/api/aiConfig.ts`
- Create: `frontend/src/features/settings/AIConfigurationSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Create: `frontend/tests/aiCapabilityConfiguration.test.mjs`

- [ ] **Step 1: Write the failing static UI contract test**

```javascript
test('AI capability settings manages models and policies without rendering secrets', () => {
  assert.match(source, /AI能力配置/)
  assert.match(source, /能力策略/)
  assert.match(source, /credential_configured/)
  assert.match(api, /\/api\/ai-config\/models/)
  assert.match(api, /\/api\/ai-config\/policies/)
  assert.doesNotMatch(source, /value=\{.*api_key/)
  assert.doesNotMatch(source, /credential\.api_key/)
})
```

- [ ] **Step 2: Run the UI test and verify it fails**

Run: `node --test frontend/tests/aiCapabilityConfiguration.test.mjs`

Expected: FAIL because the API module and section do not exist.

- [ ] **Step 3: Implement the admin UI and API client**

In `api/aiConfig.ts`, define TypeScript types matching the safe API responses and functions `listAIModels`, `createAIModel`, `updateAIModel`, `setAIModelEnabled`, `replaceAIModelCredentials`, `clearAIModelCredential`, `testAIModel`, `listAICapabilityPolicies`, and `saveAICapabilityPolicy`.

`AIConfigurationSection.tsx` must provide:

```text
模型目录
  - type filter: 对话 / 语音
  - display name, Provider, upstream model, endpoint, enabled state, revision
  - “已配置凭证” badge only; credential modal has a blank password field and clear action
  - add/edit/test/enable/disable actions

能力策略
  - one card per registered capability key with an explanatory label
  - primary-model select filtered to enabled models of the required type with configured credentials
  - ordered fallback multi-select; primary model cannot be added to fallback
  - timeout/max-attempts controls; disabled incomplete policies render as “未配置”
```

Replace `<LLMConfigSection />` in `SettingsPage.tsx` with `<AIConfigurationSection />`; keep other settings sections unchanged. Preserve Chinese user-facing text in UTF-8 and do not render any legacy default-provider control.

- [ ] **Step 4: Run frontend checks**

Run: `node --test frontend/tests/aiCapabilityConfiguration.test.mjs; npm run build`

Working directory: `frontend`

Expected: the test passes and TypeScript/Vite build completes successfully.

- [ ] **Step 5: Commit the management UI**

```bash
git add frontend/src/api/aiConfig.ts frontend/src/features/settings/AIConfigurationSection.tsx frontend/src/pages/SettingsPage.tsx frontend/tests/aiCapabilityConfiguration.test.mjs
git commit -m "feat: manage AI capability policies in settings"
```

### Task 7: Route all chat capabilities through `AIService` without changing prompts or business validation

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/routers/tasks.py`
- Modify: `bowei_ai_dashboard/app/services/extractor.py`
- Modify: `bowei_ai_dashboard/app/services/work_report_agent.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_progress_review_api.py`
- Modify: `bowei_ai_dashboard/tests/test_cross_project_work_report_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`
- Create: `bowei_ai_dashboard/tests/test_ai_capability_integration.py`

- [ ] **Step 1: Write failing integration tests around capability keys, not Provider strings**

```python
def test_meeting_analysis_uses_meeting_capability(monkeypatch, seeded_meeting_db):
    captured = {}
    monkeypatch.setattr(meetings, "AIService", lambda db: FakeAIService(captured, result='{"title":"例会"}'))
    result = meetings._do_analyze(seeded_meeting_db, "transcript", "prompt", resource_id=4)
    assert result == {"title": "例会"}
    assert captured["capability_key"] == "meeting.analysis"


def test_task_extractor_uses_task_extraction_capability(fake_ai_service):
    result = extractor.extract_task_outline("完成上线验收", ai_service=fake_ai_service)
    assert result["engine"] == "task.extraction"
    assert fake_ai_service.calls[0].capability_key == "task.extraction"


def test_project_init_preserves_injected_test_caller_without_selecting_a_provider():
    result = generate_project_init_draft([chunk("实施交付")], [], [], llm_call=lambda prompt: '{"tasks": []}')
    assert result is not None
```

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run: `python -m pytest tests/test_ai_capability_integration.py tests/test_meeting_draft_review.py tests/test_cross_project_work_report_agent.py tests/test_project_init_ai_agent.py -q`

Expected: FAIL because current helpers still accept/select a Provider string.

- [ ] **Step 3: Replace configuration/provider selection, retaining existing Prompt and result code**

Make these interface changes:

```python
# meetings.py
def _do_analyze(db: Session, text: str, prompt: str, *, resource_id: int | None = None) -> dict:
    result = AIService(db).invoke_chat(
        Capability.MEETING_ANALYSIS,
        prompt,
        AIInvocationContext(resource_type="meeting", resource_id=resource_id),
    )
    return _extract_json_blob(result.text)

# extractor.py
def extract_tasks(text: str, project_names: list[str] | None = None, *, ai_service: AIService | None = None) -> dict:
    raise NotImplementedError

def extract_update(source_type: str, transcript_text: str, submitter: str | None = None, ceo_name: str = "", *, require_llm: bool = False, user_subtasks: list[dict] | None = None, ai_service: AIService | None = None) -> dict:
    raise NotImplementedError

# work_report_agent.py
def extract_work_report_agent(transcript_text: str, candidates: list[dict], *, ai_call: Callable[[str], dict], submitter: str | None = None) -> dict:
    raise NotImplementedError

# project_init_ai_agent.py
def generate_project_init_draft(chunks: Iterable[SourceChunk | dict[str, Any]], existing_people: Iterable[PersonCandidate | dict[str, Any]], existing_tasks: Iterable[dict[str, Any]], llm_call: Callable[[str], str] | None = None, ai_service: AIService | None = None) -> ProjectInitAiResult:
    raise NotImplementedError
```

At the router/service composition points, instantiate `AIService(db)` and pass a small capability-bound closure into existing business helpers. Preserve all existing prompt construction, JSON extraction, evidence checks, and Pydantic validation. Replace result metadata previously called `engine` with the capability key and add `model_code`/`invocation_log_id` only when provided by the service; do not expose credentials. Remove `_pick_provider`, `resolve_provider`, `get_provider_config`, direct `OpenAI`, and direct `anthropic` use from these chat paths.

- [ ] **Step 4: Run all chat capability regression suites**

Run: `python -m pytest tests/test_ai_capability_integration.py tests/test_meeting_draft_review.py tests/test_meeting_progress_review_api.py tests/test_cross_project_work_report_agent.py tests/test_extractor_rule_regressions.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q`

Expected: PASS; test doubles assert the correct capability keys and no test needs a live Provider credential.

- [ ] **Step 5: Commit the chat migration**

```bash
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/routers/tasks.py bowei_ai_dashboard/app/services/extractor.py bowei_ai_dashboard/app/services/work_report_agent.py bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_meeting_draft_review.py bowei_ai_dashboard/tests/test_meeting_progress_review_api.py bowei_ai_dashboard/tests/test_cross_project_work_report_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_ai_capability_integration.py
git commit -m "refactor: route chat features through AI capabilities"
```

### Task 8: Route file and realtime transcription through the ASR capability

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/transcribe.py`
- Modify: `bowei_ai_dashboard/app/services/realtime_asr.py`
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_security.py`
- Modify: `bowei_ai_dashboard/tests/test_transcribe_stream_protocol.py`
- Create: `bowei_ai_dashboard/tests/test_ai_asr_capability_integration.py`

- [ ] **Step 1: Write failing ASR routing tests**

```python
def test_file_transcription_uses_speech_realtime_capability(monkeypatch):
    captured = {}
    monkeypatch.setattr(transcribe, "AIService", lambda db: FakeAIService(captured, transcript="转写内容"))
    result = asyncio.run(transcribe.transcribe(file=upload("a.mp3", b"audio"), current_user="member", db=object()))
    assert result["text"] == "转写内容"
    assert captured["capability_key"] == "speech.realtime"


def test_realtime_stream_reports_not_configured_without_reading_legacy_provider(monkeypatch):
    websocket = _RouteWebSocket()
    monkeypatch.setattr(transcribe, "get_session_user", lambda _session_id: "member")
    monkeypatch.setattr(transcribe, "AIService", lambda db: FakeAIService(error=AICapabilityNotConfigured()))
    asyncio.run(transcribe.transcribe_stream(websocket, db=object()))
    assert websocket._sent[0]["code"] == "ASR_NOT_CONFIGURED"
```

- [ ] **Step 2: Run the ASR tests and verify they fail**

Run: `python -m pytest tests/test_ai_asr_capability_integration.py tests/test_transcribe_stream_protocol.py tests/test_production_runtime_security.py -q`

Expected: FAIL because the router still calls `get_provider_config("dashscope")`.

- [ ] **Step 3: Move ASR resolution behind the capability service**

Change `transcribe()` to accept `db: Session = Depends(get_db)` and call:

```python
result = await asyncio.to_thread(
    AIService(db).transcribe_file,
    Capability.SPEECH_REALTIME,
    content,
    filename,
    AIInvocationContext(actor=current_user, resource_type="transcription_file"),
)
```

For WebSocket startup, replace the DashScope key lookup with `AIService(db).create_realtime_asr_session(...)`; preserve the existing ASR protocol, authenticated-user handling, cleanup, and `DashScopeRealtimeAsr` state machine. The service owns API-key decryption and supplies the already-initialized session handle. Map `AICapabilityNotConfigured` to the current safe `ASR_NOT_CONFIGURED` websocket response; map retry exhaustion to `ASR_PROVIDER_ERROR`; never include a Provider exception in the websocket message.

Delete `_do_transcribe` after its body is moved to `DashScopeFileASRAdapter`. `realtime_asr.py` must receive no configuration lookup; retain it as an SDK session implementation that gets a short-lived API key only from the adapter.

- [ ] **Step 4: Run ASR regressions**

Run: `python -m pytest tests/test_ai_asr_capability_integration.py tests/test_transcribe_stream_protocol.py tests/test_realtime_asr.py tests/test_asr_context.py tests/test_asr_settings.py tests/test_production_runtime_security.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the ASR migration**

```bash
git add bowei_ai_dashboard/app/routers/transcribe.py bowei_ai_dashboard/app/services/realtime_asr.py bowei_ai_dashboard/tests/test_production_runtime_security.py bowei_ai_dashboard/tests/test_transcribe_stream_protocol.py bowei_ai_dashboard/tests/test_ai_asr_capability_integration.py
git commit -m "refactor: route ASR through AI capabilities"
```

### Task 9: Add startup safeguards, controlled migration mode, deployment instructions, and rollback controls

**Files:**
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `docker-compose.prod.yml`
- Modify: `Dockerfile.backend`
- Modify: `.env.production.example`
- Modify: `docs/production-runtime-contract.md`
- Modify: `docs/tencent-cvm-first-deploy.md`
- Modify: `bowei_ai_dashboard/tests/test_production_deployment_contract.py`
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_contract.py`
- Create: `bowei_ai_dashboard/tests/test_ai_capability_startup.py`

- [ ] **Step 1: Write failing startup and deployment contract tests**

```python
def test_production_database_mode_requires_a_valid_ai_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AI_CAPABILITY_CENTER_MODE", "database")
    monkeypatch.delenv("AI_CONFIG_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="AI_CONFIG_ENCRYPTION_KEY"):
        main._startup()


def test_production_compose_passes_key_without_mounting_legacy_json_in_database_mode():
    backend = _service_block(_read(COMPOSE_PATH), "backend", "frontend")
    assert "AI_CAPABILITY_CENTER_MODE: database" in backend
    assert "AI_CONFIG_ENCRYPTION_KEY" not in backend  # supplied only by env_file
    assert "llm_configs.json:/app/llm_configs.json" not in backend
```

- [ ] **Step 2: Run the deployment tests and verify they fail**

Run: `python -m pytest tests/test_ai_capability_startup.py tests/test_production_deployment_contract.py tests/test_production_runtime_contract.py -q`

Expected: FAIL because startup and Compose still depend on `llm_configs.json`.

- [ ] **Step 3: Implement explicit modes and the production handoff**

Define these exact values in startup configuration:

```text
AI_CAPABILITY_CENTER_MODE=database          # normal mode; required in production after migration
AI_CAPABILITY_CENTER_MODE=legacy-rollback   # emergency only; requires AI_LEGACY_ROLLBACK_ACKNOWLEDGED=true
```

`database` validates `AI_CONFIG_ENCRYPTION_KEY` with `AICredentialCipher` during `_startup`, verifies that all four AI tables exist, and fails fast with a safe migration instruction if not. `legacy-rollback` is rejected unless both acknowledgement and `/app/llm_configs.json` exist; it writes one `OperationLog` event named `ai_capability_legacy_rollback` and exposes no new configuration mutations. There is no implicit fallback from database mode to legacy mode.

Update the production Compose contract to use `AI_CAPABILITY_CENTER_MODE: database`, remove the `llm_configs.json` volume from the backend and permission-init service, and remove the `touch`/`chown` file setup from `Dockerfile.backend`. Add `AI_CONFIG_ENCRYPTION_KEY` to `.env.production.example` as an empty required placeholder and document generation:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Document the exact release order: backup the legacy JSON outside the container; deploy migration-capable image with the JSON mounted only for a one-time admin migration command; run `alembic upgrade head`; call the admin migration endpoint or approved maintenance command; inspect its sanitized report; set `AI_CAPABILITY_CENTER_MODE=database`; remove the JSON mount in the subsequent normal deployment; retain the backup offline for emergency rollback. Do not document or allow a file containing a plaintext key to be committed.

- [ ] **Step 4: Run startup/deployment contracts**

Run: `python -m pytest tests/test_ai_capability_startup.py tests/test_production_deployment_contract.py tests/test_production_runtime_contract.py tests/test_backend_image_dependency_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit deployment hardening**

```bash
git add bowei_ai_dashboard/app/main.py docker-compose.prod.yml Dockerfile.backend .env.production.example docs/production-runtime-contract.md docs/tencent-cvm-first-deploy.md bowei_ai_dashboard/tests/test_ai_capability_startup.py bowei_ai_dashboard/tests/test_production_deployment_contract.py bowei_ai_dashboard/tests/test_production_runtime_contract.py
git commit -m "feat: secure AI capability configuration deployment"
```

### Task 10: Remove normal-path legacy configuration and prove no AI runtime bypass remains

**Files:**
- Delete: `bowei_ai_dashboard/app/llm_config.py`
- Delete: `bowei_ai_dashboard/app/routers/llm_config.py`
- Delete: `frontend/src/api/llmConfig.ts`
- Delete: `frontend/src/features/settings/LLMConfigSection.tsx`
- Delete: `bowei_ai_dashboard/tests/test_llm_config_persistence.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/settings.py`
- Modify: `bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py`
- Create: `bowei_ai_dashboard/tests/test_ai_runtime_bypass_contract.py`
- Modify: `frontend/tests/llmConfigSection.test.mjs`

- [ ] **Step 1: Write failing no-bypass contract tests**

```python
from pathlib import Path


def test_application_runtime_has_no_legacy_provider_selection_or_file_config_reads():
    runtime_files = list(Path("app").rglob("*.py"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
    assert "def _pick_provider" not in source
    assert "resolve_provider(" not in source
    assert "get_provider_config(" not in source
    assert "llm_configs.json" not in source
    assert "AIService(" in source


def test_frontend_has_no_legacy_llm_config_client_or_default_provider_control():
    assert not Path("../frontend/src/api/llmConfig.ts").exists()
    assert not Path("../frontend/src/features/settings/LLMConfigSection.tsx").exists()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_ai_runtime_bypass_contract.py -q`

Expected: FAIL because legacy modules and direct selectors still exist.

- [ ] **Step 3: Remove the old normal path and retain only the isolated rollback reader**

Delete the legacy router/client/components/tests and remove their imports, endpoint registration, public route exception, and file-based LLM helper functions. Move the minimal JSON read function needed by `ai_legacy_migration.py` and `legacy-rollback` into that service as a private helper; no business router or service may import it. Remove obsolete environment-variable Provider overrides from `settings.py`; preserve only standard deployment settings and `AI_CONFIG_ENCRYPTION_KEY` validation.

Replace `frontend/tests/llmConfigSection.test.mjs` with `frontend/tests/aiCapabilityConfiguration.test.mjs` coverage from Task 6 so no removed path is tested. Update backend image contract tests to assert the legacy JSON file is not created or writable.

- [ ] **Step 4: Run static bypass checks, full affected backend suite, and frontend build**

Run: `python -m pytest tests/test_ai_runtime_bypass_contract.py tests/test_ai_config_crypto.py tests/test_ai_config_models.py tests/test_ai_config_repository.py tests/test_ai_legacy_migration.py tests/test_ai_service.py tests/test_ai_invocation_logs.py tests/test_ai_config_api.py tests/test_ai_capability_integration.py tests/test_ai_asr_capability_integration.py tests/test_transcribe_stream_protocol.py tests/test_production_runtime_security.py tests/test_production_deployment_contract.py tests/test_backend_image_dependency_contract.py -q`

Expected: PASS.

Run: `node --test tests/aiCapabilityConfiguration.test.mjs; npm run build`

Working directory: `frontend`

Expected: PASS.

- [ ] **Step 5: Commit the legacy cleanup**

```bash
git add bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/settings.py bowei_ai_dashboard/app/ai bowei_ai_dashboard/app/services/ai_legacy_migration.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/routers/tasks.py bowei_ai_dashboard/app/routers/transcribe.py bowei_ai_dashboard/app/services/extractor.py bowei_ai_dashboard/app/services/work_report_agent.py bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/app/services/realtime_asr.py bowei_ai_dashboard/tests frontend/src frontend/tests
git commit -m "refactor: retire legacy LLM configuration path"
```

### Task 11: Run migration rehearsal, end-to-end acceptance, and release verification

**Files:**
- Create: `docs/acceptance/ai-capability-configuration-upgrade.md`
- Modify: `docs/production-runtime-contract.md`
- Create: `bowei_ai_dashboard/tests/test_ai_capability_migration_rehearsal.py`

- [ ] **Step 1: Write the end-to-end migration rehearsal test**

```python
def test_legacy_json_migrates_to_database_and_all_four_capabilities_are_resolvable(tmp_path, db):
    legacy = tmp_path / "llm_configs.json"
    legacy.write_text(json.dumps({
        "default_provider": "dashscope",
        "dashscope": {"enabled": True, "api_key": "test-key", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    }), encoding="utf-8")
    report = import_legacy_llm_config(db, legacy, cipher_key=TEST_FERNET_KEY)
    assert report.policy_states == {
        "meeting.analysis": "enabled",
        "task.extraction": "enabled",
        "project.init.analysis": "enabled",
        "speech.realtime": "enabled",
    }
    service = AIService(db, adapters=FakeAdapters())
    assert service.resolve_policy("meeting.analysis").primary_model.model_type == "chat"
    assert service.resolve_policy("speech.realtime").primary_model.model_type == "asr"
```

- [ ] **Step 2: Run the rehearsal before writing acceptance documentation**

Run: `python -m pytest tests/test_ai_capability_migration_rehearsal.py -q`

Expected: PASS.

- [ ] **Step 3: Write the acceptance runbook with exact operator checks**

Create `docs/acceptance/ai-capability-configuration-upgrade.md` containing these checks:

```text
1. Take an encrypted/offline backup of the legacy JSON and database.
2. Add AI_CONFIG_ENCRYPTION_KEY to the protected production environment file; verify it is not shown by `docker compose config` output shared outside operations.
3. Run `python -m alembic upgrade head` in bowei_ai_dashboard and verify the four ai_* tables exist.
4. As a technical admin, run the one-time migration; verify report contains no API key and records four policy states.
5. Configure/test one chat model and one ASR model; browser network responses must show only credential_configured booleans.
6. Bind each of the four capability keys to type-compatible enabled models.
7. Execute one meeting analysis, task extraction, project-init analysis, file transcription, and realtime transcription; inspect invocation logs for capability key, policy version, model code, attempt count, result, and duration.
8. Disable the primary chat model and prove a configured fallback is used on a retryable fake/provider failure; restore the primary afterwards.
9. Confirm there is no /api/llm-config route, no legacy settings card, no mounted llm_configs.json normal-path file, and no secret in application logs.
10. Record release timestamp, migration report ID, and the first successful invocation-log IDs in the deployment ticket.
```

Add a clear rollback section: only restore a database backup or deploy the immediately preceding image with `AI_CAPABILITY_CENTER_MODE=legacy-rollback` and the offline legacy JSON mounted temporarily; record the resulting `OperationLog` event; never copy a secret into source control or an interactive shell history.

- [ ] **Step 4: Run the final verification set**

Run: `python -m pytest tests/test_ai_capability_migration_rehearsal.py tests/test_ai_runtime_bypass_contract.py tests/test_ai_config_api.py tests/test_ai_service.py tests/test_ai_asr_capability_integration.py tests/test_production_deployment_contract.py -q`

Expected: PASS.

Run: `node --test tests/aiCapabilityConfiguration.test.mjs; npm run build`

Working directory: `frontend`

Expected: PASS.

- [ ] **Step 5: Commit acceptance material**

```bash
git add docs/acceptance/ai-capability-configuration-upgrade.md docs/production-runtime-contract.md bowei_ai_dashboard/tests/test_ai_capability_migration_rehearsal.py
git commit -m "docs: add AI capability upgrade acceptance runbook"
```

## Plan self-review

- **Spec coverage:** Tasks 1–4 implement typed model/credential/policy/log resources, encrypted secrets, fallback behavior, and auditing. Tasks 5–6 provide admin-only API/UI management. Tasks 7–8 migrate all four initial capability domains. Tasks 9–11 cover startup safety, one-time migration, rollback, legacy retirement, and acceptance evidence.
- **No-secret check:** Every planned response is a status or sanitized report; all actual secret reads are confined to `AICredentialCipher` + adapter invocation. The tests explicitly scan logs and UI source for secrets.
- **Boundary check:** Prompts and business result validation remain in their existing modules; Provider SDK use moves only into adapters. The plan introduces no RAG, embedding, tenant policy, or dynamic cost routing.
- **Migration graph check:** The plan pins the current Alembic head (`f5a6b7c8d9e0`) and explicitly requires updating only the parent pointer if another already-approved migration lands before implementation.
