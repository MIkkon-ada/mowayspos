# Production LLM Secret Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the production contract that LLM API keys come only from environment variables and are never persisted by the administration API.

**Architecture:** Keep non-secret provider settings in `llm_configs.json`, reject real API-key submissions in production, strip legacy file keys when production settings are saved, and ignore any residual file key at runtime. Preserve the existing development behavior.

**Tech Stack:** FastAPI, Pydantic, pytest, environment-based runtime settings.

---

### Task 1: Lock the runtime secret boundary with a regression test

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_security.py`
- Test: `bowei_ai_dashboard/tests/test_production_runtime_security.py`

- [ ] **Step 1: Add a failing test**

Add a test that sets `APP_ENV=production`, removes `DEEPSEEK_API_KEY`, stubs the stored configuration with `api_key="legacy-file-secret"`, calls `app.llm_config.get_provider_config("deepseek")`, and asserts the returned `api_key` is empty while non-secret settings remain available.

- [ ] **Step 2: Verify the test fails for the intended reason**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_production_runtime_security.py -q
```

Expected: the two existing persistence tests fail and the new runtime test fails because the legacy file key is returned.

### Task 2: Restore production persistence and runtime guards

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/llm_config.py`
- Modify: `bowei_ai_dashboard/app/llm_config.py`
- Modify: `bowei_ai_dashboard/app/settings.py`
- Test: `bowei_ai_dashboard/tests/test_production_runtime_security.py`

- [ ] **Step 1: Restore the production save guard**

Use `get_settings().app_env` in `save_config`. Reject a supplied non-mask API key with HTTP 400, without including the secret in the error.

- [ ] **Step 2: Persist only non-secret settings in production**

In production, remove `api_key` from every stored provider mapping before saving and write only `base_url`, `model`, and `enabled` for the edited provider. Keep the current masked-key preservation behavior in non-production environments.

- [ ] **Step 3: Ignore residual file keys at runtime**

In `get_provider_config`, use an empty stored API key whenever `app_env` is production. Environment overrides continue to supply the effective key.

- [ ] **Step 4: Enforce the boundary in the shared merge layer**

When `app_env` is production, filter `api_key` from file fallback data before applying environment overrides. This keeps the environment-only rule intact even if file fallback is accidentally enabled.

- [ ] **Step 5: Protect the provider test endpoint**

Reject non-mask request API keys in production, use only the environment-derived effective key, and replace provider exception details with a generic production error.

- [ ] **Step 6: Verify focused security behavior**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_production_runtime_security.py -q
```

Expected: all tests in the file pass.

### Task 3: Verify and commit

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/llm_config.py`
- Modify: `bowei_ai_dashboard/app/llm_config.py`
- Modify: `bowei_ai_dashboard/app/settings.py`
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_security.py`
- Create: `docs/superpowers/plans/2026-07-30-production-llm-secret-hardening.md`

- [ ] **Step 1: Run syntax and diff checks**

```powershell
..\.venv\Scripts\python.exe -m py_compile app\routers\llm_config.py app\llm_config.py
git diff --check
```

- [ ] **Step 2: Run the complete backend suite**

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Expected: no failures.

- [ ] **Step 3: Commit the verified fix**

```powershell
git add bowei_ai_dashboard/app/routers/llm_config.py bowei_ai_dashboard/app/llm_config.py bowei_ai_dashboard/app/settings.py bowei_ai_dashboard/tests/test_production_runtime_security.py docs/superpowers/plans/2026-07-30-production-llm-secret-hardening.md
git commit -m "fix: keep production LLM secrets environment-only"
```
