from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def test_first_run_wizard_uses_three_steps_and_chinese_model_fields():
    ui = source("features/settings/AIFirstRunWizard.tsx")

    for expected in (
        "添加模型",
        "配置 API 密钥",
        "启用业务能力",
        "模型显示名称",
        "模型 ID",
        "接口地址",
        "模型类型",
        "服务商标识",
        "DeepSeek 对话模型",
        "deepseek-chat",
        "https://api.deepseek.com",
        "保存并继续",
    ):
        assert expected in ui

    assert 'placeholder="code"' not in ui
    assert 'placeholder="display_name"' not in ui


def test_wizard_recovers_uncredentialed_model_and_keeps_key_safe():
    ui = source("features/settings/AIFirstRunWizard.tsx")

    for expected in (
        "当前模型",
        "尚未配置 API 密钥",
        'type="password"',
        "保存并测试连接",
        "继续启用能力",
        "连接失败，请检查 API Key、模型 ID 与接口地址",
    ):
        assert expected in ui

    assert 'viewBox="0 0 16 16"' in ui
    assert "setApiKey('')" in ui


def test_wizard_only_offers_eligible_models_for_capabilities():
    ui = source("features/settings/AIFirstRunWizard.tsx")

    assert "eligibleModels(models, capabilityKey)" in ui
    assert "saveAICapabilityPolicy" in ui
    assert "语音实时转写" in ui


def test_overview_retries_load_and_filters_capability_choices():
    section = source("features/settings/AIConfigurationSection.tsx")
    overview = source("features/settings/AIConfigurationOverview.tsx")

    assert "重新加载" in section
    assert "model.model_type === requiredType" in overview
    assert "model.credential_configured" in overview
    assert "会议纪要分析" in overview
    assert "任务提取" in overview
