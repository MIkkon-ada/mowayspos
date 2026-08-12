from __future__ import annotations

from pathlib import Path


def test_application_runtime_has_no_legacy_provider_selection_or_file_config_reads():
    runtime_files = list(Path("app").rglob("*.py"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)

    assert "def _pick_provider" not in source
    assert "resolve_provider(" not in source
    assert "get_provider_config(" not in source
    assert "llm_configs.json" not in source
    assert "AIService(" in source


def test_legacy_llm_configuration_modules_are_removed():
    assert not Path("app/llm_config.py").exists()
    assert not Path("app/routers/llm_config.py").exists()
    assert not Path("../frontend/src/api/llmConfig.ts").exists()
    assert not Path("../frontend/src/features/settings/LLMConfigSection.tsx").exists()
