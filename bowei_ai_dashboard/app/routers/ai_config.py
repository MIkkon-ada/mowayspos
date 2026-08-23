"""Technical-administrator API for the database-backed AI capability center."""

from __future__ import annotations

import os
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models
from ..ai.contracts import AIUpstreamError
from ..ai.repository import AIConfigurationRepository, InvalidAIModel, InvalidAIPolicy
from ..ai.service import AIService
from ..database import get_db
from ..permissions import get_current_user_name, require_tech_admin
from ..schemas import (
    AICredentialWrite,
    AIModelCreate,
    AIModelEnabledWrite,
    AIModelTestRequest,
    AIModelUpdate,
    AIPolicyWrite,
)
from ..services.ai_legacy_migration import import_legacy_llm_config


router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])


_MODEL_TEST_MESSAGES = {
    "AI_UPSTREAM_AUTH": "API Key 无效或没有调用权限，请检查后重试",
    "AI_UPSTREAM_BAD_REQUEST": "模型名称或请求参数无效，请核对模型标识",
    "AI_UPSTREAM_TIMEOUT": "上游服务响应超时，请稍后重试",
    "AI_UPSTREAM_RATE_LIMIT": "请求过于频繁或额度不足，请稍后重试",
    "AI_UPSTREAM_5XX": "上游服务暂时不可用，请稍后重试",
    "AI_UPSTREAM_CONNECTION": "无法连接上游服务，请检查网络或服务地址",
    "AI_UPSTREAM_UNKNOWN": "上游服务返回了未知错误，请稍后重试",
}


def _admin(current_user: str, db: Session) -> str:
    return require_tech_admin(current_user, db)


def _repo(db: Session) -> AIConfigurationRepository:
    try:
        return AIConfigurationRepository(db, cipher_key=os.getenv("AI_CONFIG_ENCRYPTION_KEY", ""))
    except Exception as exc:
        raise HTTPException(503, "AI_CONFIG_ENCRYPTION_KEY 未配置或无效") from exc


def _model_payload(db: Session, model: models.AIModel) -> dict:
    credential = db.query(models.AIModelCredential).filter_by(model_id=model.id).one_or_none()
    return {
        "id": model.id,
        "code": model.code,
        "display_name": model.display_name,
        "provider": model.provider,
        "model_name": model.model_name,
        "model_type": model.model_type,
        "base_url": model.base_url,
        "config": json.loads(model.config_json or "{}"),
        "enabled": model.enabled,
        "source": model.source,
        "managed_by": model.managed_by,
        "revision": model.revision,
        "credential_configured": bool(credential and credential.encrypted_api_key),
    }


def _policy_payload(policy: models.AICapabilityPolicy) -> dict:
    return {
        "id": policy.id,
        "capability_key": policy.capability_key,
        "primary_model_id": policy.primary_model_id,
        "fallback_model_ids": json.loads(policy.fallback_model_ids_json or "[]"),
        "timeout_seconds": policy.timeout_seconds,
        "max_attempts": policy.max_attempts,
        "policy_version": policy.policy_version,
        "enabled": policy.enabled,
    }


@router.get("/models")
def list_models(current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    return [_model_payload(db, row) for row in db.query(models.AIModel).order_by(models.AIModel.id).all()]


@router.post("/models", status_code=status.HTTP_201_CREATED)
def create_model(payload: AIModelCreate, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    try:
        model = _repo(db).create_model(**payload.model_dump())
        db.commit()
        return _model_payload(db, model)
    except (InvalidAIModel, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.put("/models/{model_id}")
def update_model(model_id: int, payload: AIModelUpdate, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    try:
        model = _repo(db).update_model(model_id, **payload.model_dump(exclude_none=True))
        db.commit()
        return _model_payload(db, model)
    except (InvalidAIModel, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.patch("/models/{model_id}/enabled")
def set_model_enabled(model_id: int, payload: AIModelEnabledWrite, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    return update_model(model_id, AIModelUpdate(enabled=payload.enabled), current_user, db)


@router.put("/models/{model_id}/credentials")
def replace_credentials(model_id: int, payload: AICredentialWrite, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    try:
        _repo(db).replace_credential(model_id, api_key=payload.api_key, app_secret=payload.app_secret)
        db.commit()
        return {"ok": True}
    except InvalidAIModel as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.delete("/models/{model_id}/credentials/{field}")
def clear_credential(model_id: int, field: str, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    try:
        _repo(db).clear_credential_field(model_id, field)
        db.commit()
        return {"ok": True}
    except InvalidAIModel as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/models/{model_id}/test")
def test_model(model_id: int, payload: AIModelTestRequest, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    model = db.get(models.AIModel, model_id)
    if model is None:
        raise HTTPException(404, "AI 模型不存在")
    if model.model_type != "chat":
        raise HTTPException(422, "仅支持测试对话模型")
    try:
        key = payload.temporary_api_key
        service = AIService(db)
        key = key or service._credential(model.id)
        from ..ai.adapters import DefaultAIAdapters
        DefaultAIAdapters().complete_chat(model, key, "ping", timeout_seconds=10)
        return {"ok": True, "message": "连接成功"}
    except AIUpstreamError as exc:
        return {
            "ok": False,
            "code": exc.code,
            "message": _MODEL_TEST_MESSAGES.get(exc.code, _MODEL_TEST_MESSAGES["AI_UPSTREAM_UNKNOWN"]),
        }
    except Exception:
        return {"ok": False, "code": "AI_MODEL_TEST_FAILED", "message": "模型连接测试未完成，请稍后重试"}


@router.get("/policies")
def list_policies(current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    return [_policy_payload(row) for row in db.query(models.AICapabilityPolicy).order_by(models.AICapabilityPolicy.id).all()]


@router.put("/policies/{capability_key}")
def save_policy(capability_key: str, payload: AIPolicyWrite, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    try:
        policy = _repo(db).save_policy(capability_key, **payload.model_dump())
        db.commit()
        return _policy_payload(policy)
    except (InvalidAIModel, InvalidAIPolicy, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.get("/invocation-logs")
def list_invocation_logs(capability_key: str | None = None, limit: int = Query(default=100, ge=1, le=500), current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    query = db.query(models.AIInvocationLog)
    if capability_key:
        query = query.filter_by(capability_key=capability_key)
    return [
        {column.name: getattr(row, column.name) for column in models.AIInvocationLog.__table__.columns}
        for row in query.order_by(models.AIInvocationLog.id.desc()).limit(limit).all()
    ]


@router.post("/migration/legacy-llm-config")
def migrate_legacy_config(current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _admin(current_user, db)
    legacy_path = os.getenv("AI_LEGACY_MIGRATION_FILE", "").strip()
    if not legacy_path:
        raise HTTPException(422, "请提供一次性迁移文件路径")
    try:
        report = import_legacy_llm_config(
            db,
            Path(legacy_path),
            cipher_key=os.getenv("AI_CONFIG_ENCRYPTION_KEY", ""),
        )
        db.commit()
        return report
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "旧 AI 配置迁移不可用") from exc
