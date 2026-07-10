"""LLM provider configuration management."""

from __future__ import annotations

import json
from pathlib import Path

from .settings import get_llm_effective_config

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "llm_configs.json"

PROVIDERS = {
    "anthropic": {
        "display": "Claude",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-6",
    },
    "dashscope": {
        "display": "通义千问",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "deepseek": {
        "display": "DeepSeek",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "display": "智谱GLM",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "default_model": "glm-4-flash",
    },
}


def load_configs() -> dict:
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_configs(configs: dict) -> None:
    _CONFIG_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


def get_provider_config(provider: str) -> dict:
    """Return provider config with env precedence and file fallback in dev."""
    meta = PROVIDERS.get(provider, {})
    stored = load_configs().get(provider, {})
    effective = get_llm_effective_config(
        provider,
        {
            "api_key": "",
            "base_url": meta.get("default_base_url", ""),
            "model": meta.get("default_model", ""),
        },
    )
    return {
        "api_key": effective.get("api_key", ""),
        "base_url": effective.get("base_url") or meta.get("default_base_url", ""),
        "model": effective.get("model") or meta.get("default_model", ""),
        "enabled": stored.get("enabled", False),
    }
