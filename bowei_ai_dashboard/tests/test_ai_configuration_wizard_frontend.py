from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def backend_source(path: str) -> str:
    return (ROOT / "bowei_ai_dashboard" / path).read_text(encoding="utf-8")


def test_model_management_uses_weknora_card_and_drawer_structure():
    section = source("features/settings/AIConfigurationSection.tsx")
    card = source("features/settings/AIModelCard.tsx")
    drawer = source("features/settings/AIModelDrawer.tsx")

    for expected in ("模型管理", "全部", "对话模型", "语音模型", "添加模型", "重新加载"):
        assert expected in section
    assert "AIModelCard" in section
    assert "AIModelDrawer" in section
    assert section.count("添加模型") == 1
    assert "编辑" in card
    assert "测试连接" in card
    assert "停用" in card
    assert "fixed inset-0" in drawer
    assert "right-0" in drawer


def test_model_drawer_contains_only_model_connection_fields():
    drawer = source("features/settings/AIModelDrawer.tsx")

    for expected in (
        "模型类型",
        "服务商",
        "模型名称",
        "显示名称",
        "Base URL",
        "API Key",
        "测试连接",
        "取消",
        "保存",
    ):
        assert expected in drawer
    assert 'type="password"' in drawer
    assert "replaceAIModelCredentials" in drawer
    assert "testAIModel" in drawer


def test_model_management_does_not_render_business_capability_binding():
    section = source("features/settings/AIConfigurationSection.tsx")
    combined = section + source("features/settings/AIModelDrawer.tsx") + source("features/settings/AIModelCard.tsx")

    for forbidden in (
        "会议纪要分析",
        "任务提取",
        "项目初始化分析",
        "语音实时转写",
        "listAICapabilityPolicies",
        "saveAICapabilityPolicy",
    ):
        assert forbidden not in combined


def test_provider_metadata_has_supported_providers_and_stable_code_generation():
    providers = source("features/settings/aiModelProviders.ts")

    for expected in (
        "DeepSeek",
        "阿里云 DashScope",
        "智谱 GLM",
        "Anthropic",
        "自定义 OpenAI 兼容接口",
        "https://api.deepseek.com",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "buildModelCode",
    ):
        assert expected in providers


def test_editing_credentials_never_reuses_a_saved_key():
    drawer = source("features/settings/AIModelDrawer.tsx")

    assert "credential_configured" in drawer
    assert "已配置 API Key" in drawer
    assert "仅在输入新密钥时替换" in drawer
    assert "model.api_key" not in drawer
    assert "model?.credential_configured || (persistedModelId !== null && message === '连接成功')" not in drawer


def test_ai_settings_do_not_expose_unused_global_confidence_threshold():
    settings_page = source("pages/SettingsPage.tsx")
    platform_api = source("api/platformSettings.ts")
    platform_router = backend_source("app/routers/platform_settings.py")

    for forbidden in ("AI 建议置信度", "置信度阈值", "setConfidence", "confidence,"):
        assert forbidden not in settings_page
    assert "confidence: number" not in platform_api
    assert '"confidence": 75' not in platform_router
