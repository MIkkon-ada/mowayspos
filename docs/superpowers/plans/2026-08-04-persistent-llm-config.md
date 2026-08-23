# Persistent LLM Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist administrator-managed LLM credentials and defaults across production image updates, with explicit UI selection taking priority over fallback providers.

**Architecture:** Store provider records and a top-level `default_provider` in the mounted JSON configuration. A resolver tries an explicit provider, persisted default, legacy environment provider, then enabled configured providers in declaration order; provider-specific environment values still override persisted endpoint/model/key values.

**Tech Stack:** FastAPI, Pydantic, Python JSON storage, React/TypeScript, Docker Compose, pytest, Node test runner.

---

### Task 1: Persistent default provider API

**Files:**
- Modify: `bowei_ai_dashboard/app/llm_config.py`
- Modify: `bowei_ai_dashboard/app/routers/llm_config.py`
- Create: `bowei_ai_dashboard/tests/test_llm_config_persistence.py`

- [ ] **Step 1: Write the failing persistence test**

```python
def test_production_save_keeps_key_and_default(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_config, "_CONFIG_FILE", tmp_path / "llm_configs.json")
    saved = save_config("deepseek", "secret", "https://api.deepseek.com", "deepseek-chat", True, "deepseek")
    assert saved["default_provider"] == "deepseek"
    assert saved["deepseek"]["api_key"] == "secret"
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_llm_config_persistence.py::test_production_save_keeps_key_and_default -q`

Expected: FAIL because production rejects real API keys and no default provider exists.

- [ ] **Step 3: Implement the minimal storage/API change**

Add validated `default_provider` read/write helpers. Return it from `GET /api/llm-config`; accept it only from an admin. Persist real production API keys, but retain the existing key for empty or `***` input and never return it.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/test_llm_config_persistence.py -q`

```bash
git add bowei_ai_dashboard/app/llm_config.py bowei_ai_dashboard/app/routers/llm_config.py bowei_ai_dashboard/tests/test_llm_config_persistence.py
git commit -m "feat: persist production LLM configuration"
```

### Task 2: Provider resolution precedence

**Files:**
- Modify: `bowei_ai_dashboard/app/llm_config.py`
- Modify: `bowei_ai_dashboard/app/services/work_report_agent.py`
- Modify: `bowei_ai_dashboard/app/services/extractor.py`
- Test: `bowei_ai_dashboard/tests/test_llm_config_persistence.py`

- [ ] **Step 1: Write the failing resolver test**

```python
def test_resolver_prefers_explicit_then_default_then_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert resolve_provider("anthropic") == "anthropic"
    assert resolve_provider() == "deepseek"
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_llm_config_persistence.py::test_resolver_prefers_explicit_then_default_then_env -q`

Expected: FAIL because agents read `LLM_PROVIDER` directly.

- [ ] **Step 3: Implement one resolver and use it**

Add `resolve_provider(explicit_provider=None)` that skips disabled or credential-less providers. Replace direct provider selection in `work_report_agent.py` and `extractor.py`; preserve existing no-credential failures when no candidate works.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/test_llm_config_persistence.py tests/test_cross_project_work_report_agent.py tests/test_extractor_rule_regressions.py -q`

```bash
git add bowei_ai_dashboard/app/llm_config.py bowei_ai_dashboard/app/services/work_report_agent.py bowei_ai_dashboard/app/services/extractor.py bowei_ai_dashboard/tests/test_llm_config_persistence.py
git commit -m "feat: prioritize selected LLM providers"
```

### Task 3: Administrator default-model selector

**Files:**
- Modify: `frontend/src/api/llmConfig.ts`
- Modify: `frontend/src/features/settings/LLMConfigSection.tsx`
- Create: `frontend/tests/llmConfigSection.test.mjs`

- [ ] **Step 1: Write the failing UI contract**

```js
test('settings exposes a default provider without rendering keys', () => {
  assert.match(source, /default_provider/)
  assert.match(source, /默认 LLM/)
  assert.doesNotMatch(source, /value=\{cfg\.api_key\}/)
})
```

- [ ] **Step 2: Run it**

Run: `node --test tests/llmConfigSection.test.mjs`

Expected: FAIL because no default provider selector exists.

- [ ] **Step 3: Implement UI/API plumbing**

Add a `<select>` containing enabled providers and save it through the admin API. Preserve blank/masked API-key behavior after reload.

- [ ] **Step 4: Verify and commit**

Run: `node --test tests/llmConfigSection.test.mjs; npm run build`

```bash
git add frontend/src/api/llmConfig.ts frontend/src/features/settings/LLMConfigSection.tsx frontend/tests/llmConfigSection.test.mjs
git commit -m "feat: select default LLM in settings"
```

### Task 4: Deployment contract and browser verification

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_production_deployment_contract.py`
- Modify: `docker-compose.prod.yml` only if its existing mount does not match the test

- [ ] **Step 1: Write the compose contract**

```python
def test_production_llm_config_uses_persistent_mount():
    assert "${MOWAYS_DATA_ROOT:-/data/mowayspos}/env/llm_configs.json:/app/llm_configs.json" in COMPOSE.read_text()
```

- [ ] **Step 2: Verify backend and compose contracts**

Run: `python -m pytest tests/test_llm_config_persistence.py tests/test_production_deployment_contract.py -q`

- [ ] **Step 3: Browser acceptance**

Open `/settings`, choose an enabled default LLM, save, refresh, and verify it persists while no API key is rendered.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml bowei_ai_dashboard/tests/test_production_deployment_contract.py
git commit -m "test: verify persistent LLM deployment contract"
```
