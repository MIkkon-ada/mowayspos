from app import llm_config
from app.routers import llm_config as router


def test_default_provider_persists_in_shared_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_config, "_CONFIG_FILE", tmp_path / "llm_configs.json")

    llm_config.save_configs({"default_provider": "deepseek"})

    assert llm_config.get_default_provider() == "deepseek"


def test_resolver_prefers_explicit_then_default_then_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_config, "_CONFIG_FILE", tmp_path / "llm_configs.json")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    llm_config.save_configs({
        "default_provider": "deepseek",
        "deepseek": {"enabled": True, "api_key": "deepseek-key"},
        "anthropic": {"enabled": True, "api_key": "anthropic-key"},
    })

    assert llm_config.resolve_provider("anthropic") == "anthropic"
    assert llm_config.resolve_provider() == "deepseek"


def test_production_admin_save_persists_a_real_api_key(monkeypatch):
    captured = {}
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(router, "_require_admin", lambda *_: None)
    monkeypatch.setattr(router, "load_configs", lambda: {})
    monkeypatch.setattr(router, "save_configs", lambda configs: captured.update(configs))

    router.save_config(
        "deepseek",
        router.LLMConfigPayload(api_key="secret", base_url="https://api.deepseek.com", model="deepseek-chat", enabled=True),
        current_user="admin",
        db=object(),
    )

    assert captured["deepseek"]["api_key"] == "secret"
