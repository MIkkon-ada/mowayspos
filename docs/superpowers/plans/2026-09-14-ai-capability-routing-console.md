# AI Capability Routing Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dense AI configuration section with a reference-style routing console while preserving all existing configuration APIs and behavior.

**Architecture:** Keep `AIConfigurationSection` as the data/orchestration container, but split rendering into small local view helpers for health tiles, model pool, module routes, model load, and route editor. Reuse `AIModelDrawer` for model CRUD and keep policy persistence in the existing `savePolicy` function.

**Tech Stack:** React, TypeScript, Tailwind CSS, Vitest, Testing Library, existing AI configuration API.

---

### Task 1: Add failing tests for the routing-console behavior

**Files:**
- Modify: `frontend/src/features/settings/AIConfigurationSection.test.tsx`
- Modify: `frontend/tests/aiCapabilityPolicyStructure.test.mjs` only if the structure contract needs the new route-console marker

- [ ] **Step 1: Add a fixture with two models and configured policies**

Use one chat model, one ASR model, and a configured meeting policy with one primary and one fallback model. Keep the existing empty-policy fixture for default capability coverage.

- [ ] **Step 2: Add a failing health-and-resource-pool test**

Render the section and assert it shows `AI 能力路由台`, `模块就绪度`, `模型资源池`, the model provider, and the route node labels. The current component should fail because it only renders `模型管理` and vertical policy rows.

- [ ] **Step 3: Add a failing view-switch test**

Click `按模型 · 资源负载` and assert `各模型的负载分布` and the model’s `主用于（第一顺位）` section are visible.

- [ ] **Step 4: Add a failing route-editor persistence test**

Click the meeting capability’s `编辑链路`, move the fallback model up or remove it, click `保存路由`, and assert `saveAICapabilityPolicy` receives the expected primary/fallback IDs and timeout values.

- [ ] **Step 5: Run the focused tests and verify the expected red state**

Run:

```powershell
Set-Location frontend
npm run test:unit -- --run src/features/settings/AIConfigurationSection.test.tsx
```

Expected: the new routing-console assertions fail against the current vertical layout.

### Task 2: Implement the reference-style routing console

**Files:**
- Modify: `frontend/src/features/settings/AIConfigurationSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add derived status and usage helpers**

Implement pure helpers for model status, capability status, model dependency count, primary usage count, eligible models, and route display labels. Use `enabled` and `credential_configured` only; do not invent a live connection status that the API does not provide.

- [ ] **Step 2: Add the health strip**

Render four compact cards: ready capabilities over total, configured/usable models over total, highest primary usage, and ASR availability. The ASR card uses the warning state and `去接入语音模型` action when no enabled ASR model exists.

- [ ] **Step 3: Add the two-column workbench shell**

Render the left model pool and the right route view inside the AI section. Keep `AIModelDrawer` for add/edit, and add the reference-style segmented view switch.

- [ ] **Step 4: Add module route nodes and warnings**

Render each capability with title, description, system key, status chip, primary-to-fallback nodes, and a concise warning for missing or unconfigured models. Keep the existing timeout inputs in the route editor rather than displaying them in every row.

- [ ] **Step 5: Add the route editor drawer**

Add state for the open capability and draft order. Support add, remove, move up, move down, cancel, and save. Save through the existing `saveAICapabilityPolicy` contract and refresh all derived data after success.

- [ ] **Step 6: Add the model-centric view**

Render model cards with coverage percentage, primary capabilities, fallback capabilities, and a dashed warning block for unconfigured capabilities.

- [ ] **Step 7: Allow the AI section to use the reference width**

Change the SettingsPage content wrapper to use `max-w-6xl` for `effectiveSection === 'ai'` and keep `max-w-3xl` for all other settings sections.

### Task 3: Refine tests and verify the implementation

**Files:**
- Modify: `frontend/src/features/settings/AIConfigurationSection.test.tsx`
- Modify: `frontend/tests/aiCapabilityPolicyStructure.test.mjs` if needed

- [ ] **Step 1: Run focused unit tests**

```powershell
Set-Location frontend
npm run test:unit -- --run src/features/settings/AIConfigurationSection.test.tsx
```

Expected: all routing-console tests pass.

- [ ] **Step 2: Run related contract tests**

```powershell
Set-Location frontend
npm run test:unit -- --run src/features/settings/AIConfigurationSection.test.tsx src/features/settings/AIModelDrawer.test.tsx
node tests/aiCapabilityPolicyStructure.test.mjs
```

Expected: all selected tests pass and the API paths for model/policy CRUD remain present.

- [ ] **Step 3: Build the frontend**

```powershell
Set-Location frontend
npm run build
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 4: Check the final diff**

```powershell
Set-Location ..
git diff --check
git status --short
```

Confirm only the AI routing console changes are attributed to this task; preserve all existing unrelated worktree changes.
