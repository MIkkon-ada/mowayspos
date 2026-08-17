# AI Model Connection Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AI 模型连接测试在缺少迁移或上游失败时的误导性反馈，并支持 DeepSeek 官方模型别名提示。

**Architecture:** Alembic 负责补齐受保护数据库的缺失表；`ai_config` 路由把适配器的安全错误码映射为固定提示；前端直接显示该提示。密钥继续只在请求体/加密凭证中使用，不进入日志或响应。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、React、TypeScript、pytest、Node test runner。

---

### Task 1: Back up and migrate the protected database

**Files:**
- Runtime data: `bowei_ai_dashboard/bowei_ai_dashboard.db`

- [ ] Create a timestamped SQLite backup with `sqlite3.Connection.backup()`.
- [ ] Run `alembic upgrade heads` with the configured `DATABASE_URL`.
- [ ] Verify the four AI configuration tables exist and the database records all Alembic heads.

### Task 2: Add failing tests for safe diagnostic results

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_ai_config_api.py`
- Modify: `frontend/tests/aiModelManagement.test.mjs`

- [ ] Add a backend test whose adapter raises `AIUpstreamError('AI_UPSTREAM_AUTH')` and expects a non-secret authentication message and code.
- [ ] Add a backend test whose adapter raises `AIUpstreamError('AI_UPSTREAM_BAD_REQUEST')` and expects a model/request message.
- [ ] Add a frontend assertion that DeepSeek metadata lists `deepseek-v4-flash、deepseek-v4-pro` and that the drawer renders the returned test message.
- [ ] Run the focused tests and confirm they fail because the endpoint currently always returns `AI_MODEL_TEST_FAILED` and the old metadata remains.

### Task 3: Return classified safe test failures

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/ai_config.py`
- Modify: `frontend/src/features/settings/AIModelDrawer.tsx`
- Modify: `frontend/src/features/settings/aiModelProviders.ts`

- [ ] Map known `AIUpstreamError.code` values to fixed Chinese messages without propagating exception text.
- [ ] Preserve the generic failure only for unknown failures.
- [ ] Render the response message from `testAIModel()` and update the DeepSeek hint.
- [ ] Run focused backend/frontend tests until green.

### Task 4: Verify the repaired path

**Files:**
- Test: `bowei_ai_dashboard/tests/test_ai_config_api.py`
- Test: `frontend/tests/aiModelManagement.test.mjs`

- [ ] Run focused backend and frontend tests.
- [ ] Run the relevant AI configuration test set and frontend build.
- [ ] Open the settings page and confirm the official DeepSeek aliases are shown; test with the user-configured credentials without exposing them.
