"""Validated persistence operations for AI capability configuration."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app import models

from .contracts import Capability, ModelType
from .crypto import AICredentialCipher


class InvalidAIModel(ValueError):
    """Raised when model metadata cannot safely be persisted."""


class InvalidAIPolicy(ValueError):
    """Raised when a capability policy references ineligible models."""


class AIConfigurationRepository:
    def __init__(self, db: Session, *, cipher_key: str):
        self.db = db
        self._cipher = AICredentialCipher(cipher_key)

    @staticmethod
    def _normalize_model_type(model_type: str) -> str:
        try:
            return ModelType(model_type).value
        except ValueError as exc:
            raise InvalidAIModel("unsupported AI model type") from exc

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        normalized = str(base_url or "").strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidAIModel("base_url must be a valid HTTP(S) URL")
        return normalized

    @staticmethod
    def _config_json(config: dict[str, Any]) -> str:
        if not isinstance(config, dict):
            raise InvalidAIModel("model config must be an object")
        return json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _model_or_error(self, model_id: int) -> models.AIModel:
        model = self.db.get(models.AIModel, model_id)
        if model is None:
            raise InvalidAIModel("referenced AI model does not exist")
        return model

    def create_model(
        self,
        *,
        code: str,
        display_name: str,
        provider: str,
        model_name: str,
        model_type: str,
        base_url: str,
        config: dict[str, Any],
        enabled: bool,
        source: str,
    ) -> models.AIModel:
        normalized_code = str(code or "").strip()
        normalized_provider = str(provider or "").strip().lower()
        normalized_model_name = str(model_name or "").strip()
        if not normalized_code:
            raise InvalidAIModel("model code is required")
        if not str(display_name or "").strip() or not normalized_provider or not normalized_model_name:
            raise InvalidAIModel("model display name, provider, and model name are required")

        model = models.AIModel(
            code=normalized_code,
            display_name=str(display_name).strip(),
            provider=normalized_provider,
            model_name=normalized_model_name,
            model_type=self._normalize_model_type(model_type),
            base_url=self._validate_base_url(base_url),
            config_json=self._config_json(config),
            enabled=bool(enabled),
            source=str(source or "custom").strip() or "custom",
        )
        self.db.add(model)
        self.db.flush()
        return model

    def update_model(self, model_id: int, **changes: object) -> models.AIModel:
        model = self._model_or_error(model_id)
        allowed = {
            "display_name",
            "provider",
            "model_name",
            "model_type",
            "base_url",
            "config",
            "enabled",
            "source",
            "managed_by",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise InvalidAIModel("unsupported AI model update field")

        normalized: dict[str, object] = {}
        for field, value in changes.items():
            if field == "model_type":
                normalized[field] = self._normalize_model_type(str(value))
            elif field == "base_url":
                normalized[field] = self._validate_base_url(str(value))
            elif field == "config":
                normalized["config_json"] = self._config_json(value)  # type: ignore[arg-type]
            elif field == "enabled":
                normalized[field] = bool(value)
            else:
                text = str(value or "").strip()
                if field in {"display_name", "provider", "model_name"} and not text:
                    raise InvalidAIModel(f"{field} is required")
                normalized[field] = text.lower() if field == "provider" else text

        if any(getattr(model, field) != value for field, value in normalized.items()):
            for field, value in normalized.items():
                setattr(model, field, value)
            model.revision += 1
            self.db.flush()
        return model

    def replace_credential(
        self,
        model_id: int,
        *,
        api_key: str | None,
        app_secret: str | None,
    ) -> models.AIModelCredential:
        model = self._model_or_error(model_id)
        credential = (
            self.db.query(models.AIModelCredential).filter_by(model_id=model_id).one_or_none()
        )
        if credential is None:
            credential = models.AIModelCredential(model_id=model_id)
            self.db.add(credential)

        credential.encrypted_api_key = (
            self._cipher.encrypt(api_key) if api_key else ""
        )
        credential.encrypted_app_secret = (
            self._cipher.encrypt(app_secret) if app_secret else ""
        )
        model.revision += 1
        self.db.flush()
        return credential

    def clear_credential_field(self, model_id: int, field: str) -> None:
        model = self._model_or_error(model_id)
        fields = {
            "api_key": "encrypted_api_key",
            "app_secret": "encrypted_app_secret",
        }
        column = fields.get(field)
        if column is None:
            raise InvalidAIModel("unsupported credential field")
        credential = (
            self.db.query(models.AIModelCredential).filter_by(model_id=model_id).one_or_none()
        )
        if credential is not None and getattr(credential, column):
            setattr(credential, column, "")
            model.revision += 1
            self.db.flush()

    def credential_configured(self, model_id: int) -> bool:
        credential = (
            self.db.query(models.AIModelCredential).filter_by(model_id=model_id).one_or_none()
        )
        return credential is not None and bool(credential.encrypted_api_key)

    def save_policy(
        self,
        capability_key: str,
        *,
        primary_model_id: int | None,
        fallback_model_ids: list[int],
        timeout_seconds: int | None = None,
        max_attempts: int = 1,
        enabled: bool = False,
        fallback_timeout_seconds: int = 25,
    ) -> models.AICapabilityPolicy:
        try:
            required_type = Capability.required_model_type(capability_key)
        except ValueError as exc:
            raise InvalidAIPolicy(str(exc)) from exc
        if timeout_seconds is None:
            timeout_seconds = 200 if capability_key == Capability.PROJECT_INIT_ANALYSIS else 60
        if timeout_seconds <= 0:
            raise InvalidAIPolicy("timeout_seconds must be positive")
        if fallback_timeout_seconds <= 0:
            raise InvalidAIPolicy("fallback_timeout_seconds must be positive")
        if max_attempts < 1:
            raise InvalidAIPolicy("max_attempts must be at least one")
        if len(fallback_model_ids) != len(set(fallback_model_ids)):
            raise InvalidAIPolicy("duplicate fallback models are not allowed")
        if primary_model_id is not None and primary_model_id in fallback_model_ids:
            raise InvalidAIPolicy("duplicate fallback includes the primary model")

        primary = (
            self._model_or_error(primary_model_id) if primary_model_id is not None else None
        )
        references = [model for model in [primary] if model is not None]
        references.extend(self._model_or_error(model_id) for model_id in fallback_model_ids)
        for model in references:
            if not model.enabled:
                raise InvalidAIPolicy("referenced AI model must be enabled")
            if model.model_type != required_type.value:
                raise InvalidAIPolicy(
                    f"capability {capability_key} requires {required_type.value} model"
                )
        if enabled and primary is None:
            raise InvalidAIPolicy("enabled capability policy requires a primary model")
        if enabled and primary is not None and not self.credential_configured(primary.id):
            raise InvalidAIPolicy("enabled primary model requires a configured credential")

        fallback_json = json.dumps(fallback_model_ids, separators=(",", ":"))
        policy = (
            self.db.query(models.AICapabilityPolicy)
            .filter_by(capability_key=capability_key)
            .one_or_none()
        )
        if policy is None:
            policy = models.AICapabilityPolicy(
                capability_key=capability_key,
                primary_model_id=primary_model_id,
                fallback_model_ids_json=fallback_json,
                timeout_seconds=timeout_seconds,
                fallback_timeout_seconds=fallback_timeout_seconds,
                max_attempts=max_attempts,
                enabled=bool(enabled),
            )
            self.db.add(policy)
            self.db.flush()
            return policy

        desired = {
            "primary_model_id": primary_model_id,
            "fallback_model_ids_json": fallback_json,
            "timeout_seconds": timeout_seconds,
            "fallback_timeout_seconds": fallback_timeout_seconds,
            "max_attempts": max_attempts,
            "enabled": bool(enabled),
        }
        if any(getattr(policy, field) != value for field, value in desired.items()):
            for field, value in desired.items():
                setattr(policy, field, value)
            policy.policy_version += 1
            self.db.flush()
        return policy
