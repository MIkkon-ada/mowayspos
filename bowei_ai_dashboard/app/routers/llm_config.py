from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..llm_config import PROVIDERS, get_provider_config, load_configs, save_configs
from ..permissions import get_current_user_name, get_user_context_from_db

router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])


def _require_admin(current_user: str, db: Session):
    ctx = get_user_context_from_db(current_user, db)
    if not ctx["is_tech_admin"]:
        raise HTTPException(403, "仅技术管理员可操作模型配置")


class LLMConfigPayload(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    enabled: bool = False


@router.get("/available")
def list_available(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """返回已启用的 LLM provider 列表（不含 API Key），普通用户可访问。"""
    _ = current_user
    _ = db
    stored = load_configs()
    result = []
    for provider, meta in PROVIDERS.items():
        cfg = stored.get(provider, {})
        if cfg.get("enabled"):
            result.append({
                "provider": provider,
                "display_name": meta["display"],
                "model": cfg.get("model") or meta["default_model"],
            })
    return result


@router.get("")
def list_configs(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    stored = load_configs()
    result = []
    for provider, meta in PROVIDERS.items():
        cfg = stored.get(provider, {})
        result.append({
            "provider": provider,
            "display_name": meta["display"],
            "default_base_url": meta["default_base_url"],
            "default_model": meta["default_model"],
            "api_key_set": bool(cfg.get("api_key")),
            "base_url": cfg.get("base_url") or meta["default_base_url"],
            "model": cfg.get("model") or meta["default_model"],
            "enabled": cfg.get("enabled", False),
        })
    return result


@router.put("/{provider}")
def save_config(
    provider: str,
    payload: LLMConfigPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    if provider not in PROVIDERS:
        raise HTTPException(400, f"不支持的提供商: {provider}")
    configs = load_configs()
    existing = configs.get(provider, {})
    # 若前端回传 "***"（掩码），保留原始 Key 不覆盖
    api_key = payload.api_key if payload.api_key and payload.api_key != "***" else existing.get("api_key", "")
    configs[provider] = {
        "api_key": api_key,
        "base_url": payload.base_url,
        "model": payload.model,
        "enabled": payload.enabled,
    }
    save_configs(configs)
    return {"ok": True}


class LLMTestPayload(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@router.post("/{provider}/test")
def test_config(
    provider: str,
    payload: LLMTestPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    # 优先用表单传来的值，未填则回退到已保存配置
    saved = get_provider_config(provider)
    api_key = payload.api_key if payload.api_key and payload.api_key != "***" else saved.get("api_key", "")
    base_url = payload.base_url or saved.get("base_url", "")
    model = payload.model or saved.get("model", "")
    if not api_key:
        raise HTTPException(400, "请填写 API Key 后再测试")
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model=model,
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
        else:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url or None)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(400, f"连接失败：{e}")
